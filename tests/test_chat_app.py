"""Offline chat-interface checks with a simulated pipeline, not model quality tests.

AppTest exercises Streamlit state and widgets; it does not check browser rendering,
mobile layout, colour contrast or screen-reader behavior.
"""

from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app.py"
PRIVATE_DIAGNOSTIC = "PRIVATE_DIAGNOSTIC_SENTINEL"
RAW_PROVIDER_ERROR = "RAW_PROVIDER_ERROR_SENTINEL"


def turn(question, text="An optional booking is available.", status="supported", query=None):
    return {
        "question": question,
        "text": text,
        "status": status,
        "retrieval_question": question if query is None else query,
        "diagnostics": {"private": PRIVATE_DIAGNOSTIC, "citations": [{"source_id": "S1"}]},
    }


class ChatAppTests(unittest.TestCase):
    def setUp(self):
        from retail_copilot.pipeline import run_chat_turn

        self.real_run_chat_turn = run_chat_turn
        self.requests = []
        pipeline_patch = patch("retail_copilot.pipeline.run_chat_turn", side_effect=self.respond)
        self.pipeline = pipeline_patch.start()
        self.addCleanup(pipeline_patch.stop)

    def respond(self, question, history, settings):
        self.requests.append({"question": question, "history": deepcopy(history)})
        return turn(question)

    def start_app(self):
        app = AppTest.from_file(APP_PATH, default_timeout=15).run()
        self.assertFalse(app.exception)
        return app

    def submit(self, app, question):
        app.chat_input(key="chat_input").set_value(question).run()
        self.assertFalse(app.exception)
        return app

    def chat_text(self, app):
        return ["\n".join(element.value for element in message.get("text"))
                for message in app.chat_message]

    def visible_text(self, app):
        return "\n".join(str(element.value)
                         for kind in ("text", "markdown", "caption", "error", "warning", "info")
                         for element in app.get(kind))

    def assert_no_evidence_controls(self, app):
        self.assertFalse(app.get("expander"))
        labels = " ".join(button.label.lower() for button in app.button)
        for forbidden in ("source", "supporting polic", "policy library", "how the answer"):
            self.assertNotIn(forbidden, labels)
        visible = self.visible_text(app)
        self.assertNotIn(PRIVATE_DIAGNOSTIC, visible)
        self.assertNotIn("[S1]", visible)

    def test_initial_render_has_chat_controls_without_service_calls_or_evidence_panels(self):
        app = self.start_app()
        self.pipeline.assert_not_called()
        self.assertEqual(len(app.chat_input), 1)
        self.assertEqual(app.chat_input[0].key, "chat_input")
        for key in ("new_chat", "starter_sim", "starter_authority", "starter_roaming"):
            self.assertIsNotNone(app.button(key=key))
        self.assertFalse(app.chat_message)
        self.assertEqual(app.session_state["chat_turns"], [])
        self.assertIn("Your policy companion", self.visible_text(app))
        self.assertNotIn("Don't enter customer names, phone numbers, or account details.", self.visible_text(app))
        self.assertIn("Policy guidance", self.visible_text(app))
        self.assertNotIn("Policy guidance", [button.label for button in app.button])
        self.assertNotIn("fictional", self.visible_text(app).lower())
        self.assert_no_evidence_controls(app)

    def test_submit_adds_one_exchange_and_plain_rerun_does_not_repeat_request(self):
        app = self.start_app()
        self.submit(app, "Do I need a SIM appointment?")
        self.assertEqual(self.pipeline.call_count, 1)
        self.assertEqual([message.name for message in app.chat_message], ["user", "assistant"])
        self.assertEqual(self.chat_text(app), ["Do I need a SIM appointment?", "An optional booking is available."])
        self.assertEqual(self.requests[0]["history"], [])
        self.assertEqual(len(app.session_state["chat_turns"]), 1)
        self.assertIn("citations", app.session_state["chat_turns"][0]["diagnostics"])
        self.assert_no_evidence_controls(app)
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(self.pipeline.call_count, 1)
        self.assertEqual(len(app.chat_message), 2)

    def test_starters_submit_once_through_the_same_pipeline(self):
        for key in ("starter_sim", "starter_authority", "starter_roaming"):
            with self.subTest(starter=key):
                app = self.start_app()
                calls_before = self.pipeline.call_count
                app.button(key=key).click().run()
                self.assertFalse(app.exception)
                self.assertEqual(self.pipeline.call_count, calls_before + 1)
                self.assertTrue(self.requests[-1]["question"].strip())
                self.assertEqual(self.requests[-1]["history"], [])
                self.assertEqual(len(app.chat_message), 2)
                app.run()
                self.assertEqual(self.pipeline.call_count, calls_before + 1)

    def test_followup_receives_sanitized_recent_user_context(self):
        app = self.start_app()
        self.submit(app, "Do I need a SIM appointment?")
        self.submit(app, "Can I book one anyway?")
        self.assertEqual(self.pipeline.call_count, 2)
        self.assertEqual(self.requests[-1]["history"], [{
            "question": "Do I need a SIM appointment?",
            "retrieval_question": "Do I need a SIM appointment?",
            "status": "supported",
        }])
        self.assertEqual(len(app.chat_message), 4)
        self.assert_no_evidence_controls(app)

    def test_thanks_keeps_the_conversation_and_prior_question_for_followup(self):
        app = self.start_app()
        question = "Do I need a SIM appointment?"
        self.submit(app, question)
        def acknowledge_without_services(question, history, settings):
            # Scope the network guard to our pipeline; AppTest itself needs a
            # local socket pair to initialise its Windows event loop.
            with patch("socket.socket.connect", side_effect=AssertionError("No network for thanks")), patch(
                "retail_copilot.pipeline.resolve_question", side_effect=AssertionError("No rewrite for thanks"),
            ):
                return self.real_run_chat_turn(question, history, settings)

        self.pipeline.side_effect = acknowledge_without_services
        self.submit(app, "OK thanks")
        self.assertEqual(self.chat_text(app), [
            question, "An optional booking is available.", "OK thanks", "You're welcome!",
        ])
        self.assertEqual(app.session_state["chat_turns"][-1]["status"], "acknowledgement")
        self.assertNotIn("What would you like to check?", self.visible_text(app))
        self.assertEqual([button.key for button in app.button], ["new_chat"])
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.chat_message), 4)
        self.assertEqual(self.pipeline.call_count, 2)
        self.pipeline.side_effect = self.respond
        self.submit(app, "Can I book one anyway?")
        self.assertEqual(self.requests[-1]["history"], [{
            "question": question, "retrieval_question": question, "status": "supported",
        }])
        self.assertEqual(len(app.chat_message), 6)

    def test_acknowledgement_does_not_revive_context_across_error_or_window(self):
        acknowledgement = turn("Thanks", "You're welcome!", "acknowledgement")
        acknowledgement["retrieval_question"] = None
        old = turn("Do I need a SIM appointment?")
        failed = turn("What about roaming?", "Please try again.", "error")
        for saved in ([old, failed, acknowledgement], [old] + [acknowledgement] * 3):
            with self.subTest(history=saved):
                app = self.start_app()
                app.session_state["chat_turns"] = deepcopy(saved)
                app.run()
                self.submit(app, "Can I book one anyway?")
                self.assertEqual(self.requests[-1]["history"], [])
                self.assertEqual(len(app.chat_message), 2 * (len(saved) + 1))

    def test_history_window_stops_at_error_and_never_sends_assistant_text(self):
        app = self.start_app()
        saved = [
            turn("Old question one", "OLD_ASSISTANT_SENTINEL"),
            turn("Old question two", "OLD_ASSISTANT_SENTINEL"),
            turn("Recent clear question", "RECENT_ASSISTANT_SENTINEL"),
            turn("A failed request", "SAFE_ERROR_SENTINEL", status="error"),
            turn("Can I replace it?", "Which item?", status="needs_clarification"),
        ]
        saved[-1]["retrieval_question"] = None
        app.session_state["chat_turns"] = saved
        app.run()
        self.submit(app, "I mean the physical SIM.")
        self.assertEqual(self.requests[-1]["history"], [
            {"question": "Can I replace it?", "retrieval_question": None, "status": "needs_clarification"},
        ])
        for item in self.requests[-1]["history"]:
            self.assertEqual(set(item), {"question", "retrieval_question", "status"})

    def test_clarification_is_only_a_question_and_rerun_does_not_answer_it(self):
        app = self.start_app()
        clarification = turn("Can I replace it?", "What would you like to replace, and what happened to it?", "needs_clarification")
        clarification["retrieval_question"] = None
        self.pipeline.side_effect = None
        self.pipeline.return_value = clarification
        self.submit(app, "Can I replace it?")
        self.assertEqual(self.chat_text(app), [clarification["question"], clarification["text"]])
        self.assertEqual(app.session_state["chat_turns"][0]["status"], "needs_clarification")
        self.assert_no_evidence_controls(app)
        app.run()
        self.assertEqual(self.pipeline.call_count, 1)

    def test_known_failure_after_success_does_not_repeat_previous_answer(self):
        from retail_copilot.pipeline import ChatError

        app = self.start_app()
        self.submit(app, "Do I need a SIM appointment?")
        self.pipeline.side_effect = ChatError("The policy service is temporarily unavailable.")
        self.submit(app, "What about roaming?")
        self.assertEqual(self.pipeline.call_count, 2)
        self.assertEqual(self.chat_text(app).count("An optional booking is available."), 1)
        self.assertEqual(app.session_state["chat_turns"][-1]["status"], "error")
        self.assertIn("temporarily unavailable", self.visible_text(app))
        app.run()
        self.assertEqual(self.pipeline.call_count, 2)

        self.pipeline.side_effect = self.respond
        self.submit(app, "Can I use it overseas?")
        self.assertEqual(self.requests[-1]["history"], [])

    def test_unexpected_exception_is_not_exposed_to_user(self):
        app = self.start_app()
        self.pipeline.side_effect = RuntimeError(RAW_PROVIDER_ERROR)
        self.submit(app, "What about roaming?")
        self.assertEqual(app.session_state["chat_turns"][-1]["status"], "error")
        self.assertNotIn(RAW_PROVIDER_ERROR, self.visible_text(app))
        self.assertNotIn("Traceback", self.visible_text(app))
        self.assertTrue(app.session_state["chat_turns"][-1]["text"].strip())
        self.assertIn("try again", self.visible_text(app).lower())
        self.assertIn("copilot support", self.visible_text(app).lower())
        for term in ("ollama", "pinecone", ".env", "api key", "config/"):
            self.assertNotIn(term, self.visible_text(app).lower())

    def test_setup_failure_gives_colleague_guidance_without_developer_details(self):
        with patch("retail_copilot.documents.load_settings", side_effect=ValueError(RAW_PROVIDER_ERROR)):
            app = self.start_app()
        self.assertTrue(app.error)
        self.assertIn("copilot support", self.visible_text(app).lower())
        for term in (RAW_PROVIDER_ERROR, "Ollama", "Pinecone", "config/settings.toml", ".env"):
            self.assertNotIn(term, self.visible_text(app))
        self.pipeline.assert_not_called()

    def test_long_answer_keeps_complete_paragraphs_and_followup_input(self):
        app = self.start_app()
        paragraphs = [f"Condition {i}: " + "Example guidance for interface testing. " * 12
                      for i in range(1, 7)]
        answer = "\n\n".join(paragraphs) + "\n\n" + "LongIdentifier" * 20 + "\n\nFinal condition: do not omit this ending."
        self.pipeline.side_effect = lambda q, history, settings: turn(q, answer)
        self.submit(app, "Please explain the policy conditions.")
        self.assertEqual(self.chat_text(app)[-1], answer)
        self.assertTrue(app.chat_message[-1].get("text")[0].proto.wrap)
        self.assertEqual(len(app.chat_input), 1)
        self.assert_no_evidence_controls(app)
        self.pipeline.side_effect = self.respond
        self.submit(app, "What about the final condition?")
        self.assertEqual(self.chat_text(app)[1], answer)
        self.assertEqual(len(app.chat_message), 4)

    def test_action_limitation_is_shown_as_chat_without_execution_controls(self):
        app = self.start_app()
        answer = "I can explain the policy, but I cannot waive a bill or change an account."
        self.pipeline.side_effect = lambda q, history, settings: turn(q, answer, "action_not_supported")
        self.submit(app, "Can you waive this bill?")
        self.assertEqual(self.chat_text(app)[-1], answer)
        self.assertEqual(app.session_state["chat_turns"][-1]["status"], "action_not_supported")
        self.assertEqual([button.key for button in app.button], ["new_chat"])
        self.assert_no_evidence_controls(app)
        app.run()
        self.assertEqual(self.pipeline.call_count, 1)

    def test_new_chat_clears_turns_and_followup_context_without_a_service_call(self):
        app = self.start_app()
        self.submit(app, "Do I need a SIM appointment?")
        self.submit(app, "Can I book one anyway?")
        calls_before = self.pipeline.call_count
        app.button(key="new_chat").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(self.pipeline.call_count, calls_before)
        self.assertEqual(app.session_state["chat_turns"], [])
        self.assertFalse(app.chat_message)
        self.assertIn(app.session_state["chat_input"], (None, ""))
        self.assertIsNotNone(app.button(key="starter_sim"))
        self.submit(app, "What about roaming?")
        self.assertEqual(self.requests[-1]["history"], [])

    def test_user_and_assistant_html_are_plain_text_not_markdown_or_html(self):
        app = self.start_app()
        question = '<img src="https://example.invalid/tracker" onerror="alert(1)">'
        answer = '<script>alert("fictional")</script> **Not a formatted claim**'
        self.pipeline.side_effect = lambda q, history, settings: turn(q, answer)
        self.submit(app, question)
        self.assertEqual(self.chat_text(app), [question, answer])
        for message in app.chat_message:
            self.assertFalse(message.get("markdown"))
            self.assertFalse(message.get("html"))
            self.assertFalse(message.get("imgs"))
        self.assert_no_evidence_controls(app)

    def test_whitespace_is_ignored_and_question_input_has_a_length_limit(self):
        app = self.start_app()
        self.assertGreater(app.chat_input[0].proto.max_chars, 0)
        self.submit(app, "   ")
        self.pipeline.assert_not_called()
        self.assertFalse(app.chat_message)
        self.assertEqual(app.session_state["chat_turns"], [])

    def test_completed_submission_keeps_at_most_thirty_displayed_turns(self):
        app = self.start_app()
        app.session_state["chat_turns"] = [turn(f"Question {i}", f"Answer {i}") for i in range(30)]
        app.run()
        self.submit(app, "Newest question")
        saved = app.session_state["chat_turns"]
        self.assertEqual(len(saved), 30)
        self.assertEqual(saved[0]["question"], "Question 1")
        self.assertEqual(saved[-1]["question"], "Newest question")
        self.assertEqual(len(app.chat_message), 60)
        self.assertNotIn("Question 0", self.chat_text(app))


if __name__ == "__main__":
    unittest.main()
