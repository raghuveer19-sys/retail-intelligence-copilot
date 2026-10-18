"""Offline checks for bounded follow-ups and safe clarification before search."""

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from retail_copilot import conversation
from retail_copilot.documents import load_settings


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.settings = load_settings()
        self.settings["conversation"] = {"max_history_turns": 3, "max_question_characters": 1000,
                                         "max_history_characters": 4000}
        self.question = "Can I book one anyway?"
        self.previous = "Do I need an appointment for a physical SIM replacement?"
        self.rewritten = "Can I book an appointment for a physical SIM replacement anyway?"
        self.history = [{"question": self.previous, "retrieval_question": self.previous,
                         "text": "PRIVATE_ASSISTANT_ANSWER", "diagnostics": {"secret": "PRIVATE_DIAGNOSTIC"}}]
        self.no_network = patch("socket.socket.connect", side_effect=AssertionError("No network allowed"))
        self.no_network.start()
        self.addCleanup(self.no_network.stop)

    def response(self, rewritten=None, **updates):
        result = {
            "model": self.settings["generation"]["model"], "done": True, "done_reason": "stop",
            "message": {"role": "assistant", "content": json.dumps({
                "status": "resolved", "retrieval_question": rewritten or self.rewritten, "history_turn": 0})},
            "prompt_eval_count": 100, "eval_count": 50,
        }
        result.update(updates)
        return result

    def resolve(self, question=None, history=None, response=None, settings=None):
        with patch.object(conversation, "inspect_model", return_value={"think": False}) as inspect, patch.object(
            conversation, "request_local_json", return_value=response or self.response(),
        ) as request:
            result = conversation.resolve_question(question or self.question,
                                                   self.history if history is None else history,
                                                   settings or self.settings)
        return result, inspect, request

    def assert_clarification(self, result):
        self.assertIsNone(result["retrieval_question"])
        self.assertIsInstance(result["clarifying_question"], str)
        self.assertTrue(result["clarifying_question"].endswith("?"))
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_standalone_questions_bypass_model_and_ignore_old_topic(self):
        for question in ("What identification is required for a SIM replacement?",
                         "What does policy SIM-1024 say?", "How do I enable roaming?",
                         "Can I replace my SIM if it is damaged?", "What is the weather in Sydney?",
                         "Can I replace this SIM?", "Can I return that device?",
                         "What do these plans include?", "Can I replace one SIM?"):
            with self.subTest(question=question):
                result, inspect, request = self.resolve(question)
                self.assertEqual(result["retrieval_question"], question)
                self.assertIsNone(result["clarifying_question"])
                self.assertIsNone(result["usage"])
                inspect.assert_not_called()
                request.assert_not_called()

    def test_explicit_action_requests_reach_answering_unchanged_without_rewrite(self):
        for question in ("Waive my outstanding bill now", "Please waive my bill",
                         "OK, thanks, refund my payment", "Cancel my mobile plan",
                         "Please activate my eSIM", "Return my phone", "Change my plan",
                         "Upgrade my plan", "Transfer my account", "Book a SIM replacement appointment",
                         "Check my bill", "Show the device return policy", "Please replace my SIM",
                         "Don't cancel my plan", "Never activate my eSIM"):
            with self.subTest(question=question):
                result, inspect, request = self.resolve(question, history=[])
                self.assertEqual(result["retrieval_question"], question)
                self.assertIsNone(result["clarifying_question"])
                self.assertIsNone(result["usage"])
                inspect.assert_not_called()
                request.assert_not_called()

    def test_actions_with_missing_objects_or_people_still_clarify(self):
        for question in ("Waive it now", "Please replace", "Cancel that", "Transfer it to her",
                         "Can I replace my SIM if she is away?",
                         "Can I replace my SIM if it is damaged and she is away?",
                         "Can I replace my SIM and phone if it is damaged?"):
            with self.subTest(question=question):
                result, inspect, request = self.resolve(question, history=[])
                self.assert_clarification(result)
                inspect.assert_not_called()
                request.assert_not_called()

    def test_execution_intent_recognises_directed_actions_without_services(self):
        with patch.object(conversation, "inspect_model") as inspect, patch.object(
            conversation, "request_local_json",
        ) as request:
            for question in (
                "Waive my outstanding bill now", "Please waive the customer's bill",
                "Refund my payment", "Pay my bill", "Activate my eSIM", "Cancel my plan",
                "Change my mobile plan", "Replace my SIM", "Book a replacement appointment",
                "Could you refund my payment?", "Would you please activate my eSIM?",
                "Will you cancel my plan?", "Please can you change my plan?",
                "I want you to waive my fee", "I need you to replace my SIM",
                "I'd like you to book an appointment", "I would like you to disconnect my SIM",
                "Thanks, please cancel my plan", "Return my phone",
            ):
                with self.subTest(question=question):
                    self.assertTrue(conversation.requests_execution(question))
            inspect.assert_not_called()
            request.assert_not_called()

    def test_execution_intent_preserves_guidance_and_eligibility_questions(self):
        for question in (
            "Can I replace my SIM?", "Could I waive a fee?", "How do I activate an eSIM?",
            "How can a colleague refund a payment?", "What is the return window for a device?",
            "Can you explain how to replace a SIM?", "Could you tell me how to pay a bill?",
            "Please explain the plan change policy", "Can you help me replace my SIM?",
            "What should I check before I activate the SIM?", "Device return", "Bill waiver",
            "Return policy for devices", "Plan change", "What happens if you waive a bill?",
        ):
            with self.subTest(question=question):
                self.assertFalse(conversation.requests_execution(question))

    def test_execution_intent_does_not_treat_quotes_or_hypotheticals_as_commands(self):
        for question in (
            '"Waive my bill now"', "'Activate my eSIM'", "“Can you cancel my plan?”",
            "A customer said 'waive my bill'. What should I say?",
            "The customer asked: can you refund my payment?",
            "Someone says waive my bill, what should I do?",
            "Suppose a customer wants you to cancel their plan",
            "If a customer asks, can you waive a bill?", "Hypothetically, activate the SIM",
            "For example, refund my payment", "What if you cancel my plan?",
        ):
            with self.subTest(question=question):
                self.assertFalse(conversation.requests_execution(question))

    def test_execution_intent_does_not_treat_negated_commands_as_requests(self):
        for question in (
            "Do not waive my bill, explain the policy", "Don't cancel my plan",
            "Please don't activate my eSIM", "Never replace my SIM",
            "Could you please not refund my payment?", "I don't want you to cancel my plan",
            "Do not waive my bill and refund my payment", "Don't replace my SIM and cancel my plan",
        ):
            with self.subTest(question=question):
                self.assertFalse(conversation.requests_execution(question))

    def test_execution_intent_checks_mixed_requests_without_borrowing_objects(self):
        for question in (
            "What is the return window, and can you refund my bill?",
            "Explain the roaming policy. Then activate my SIM",
            "Can I replace my SIM? Please book an appointment",
            'What does "waive my bill" mean? Also cancel my plan',
        ):
            with self.subTest(question=question):
                self.assertTrue(conversation.requests_execution(question))
        for question in (
            "Explain the policy and show the SIM replacement guidance",
            "What is the return window, and can I return my phone?",
            "How do I activate my SIM and replace it?", "Please waive it", "Book one",
            "Replace", "", None, 42,
        ):
            with self.subTest(question=question):
                self.assertFalse(conversation.requests_execution(question))

    def test_standalone_acknowledgements_are_recognised_without_services(self):
        with patch.object(conversation, "inspect_model") as inspect, patch.object(
            conversation, "request_local_json",
        ) as request:
            for question in ("OK thanks", "Thanks!", "  THANK YOU.  ", "Okay, thank you!",
                             "Thank you very much", "Great, thanks", "Got it.", "Understood!",
                             "OK", "okay", "OK, got it", "I understand", "Okay; understood."):
                with self.subTest(question=question):
                    reply = conversation.acknowledgement_reply(question)
                    self.assertIsInstance(reply, str)
                    self.assertTrue(reply.strip())
                    self.assertNotIn("policy", reply.lower())
            inspect.assert_not_called()
            request.assert_not_called()

    def test_acknowledgements_do_not_swallow_questions_or_clarification_replies(self):
        for question in ("yes", "no", "Yes please", "No thanks", "OK thanks, can I replace my SIM?",
                         "Thanks. What about roaming?", "Okay, can you book an appointment?",
                         "Got it, how much will it cost?", "Thanks for replacing my SIM",
                         "Can you explain what 'understood' means?", "", "   ", None, 12):
            with self.subTest(question=question):
                self.assertIsNone(conversation.acknowledgement_reply(question))

    def test_public_conversation_limits_reuses_existing_validation(self):
        self.assertEqual(conversation.conversation_limits(self.settings), self.settings["conversation"])
        self.assertEqual(conversation.conversation_limits({})["max_question_characters"], 1000)
        for settings in (None, [], {"conversation": {"max_question_characters": True}}):
            with self.assertRaises(conversation.ConversationError):
                conversation.conversation_limits(settings)

    def test_pronoun_without_history_clarifies_without_model(self):
        for question in ("Can I replace it?", "How long does that take?", "Can she do it?", "What about that?"):
            result, inspect, request = self.resolve(question, history=[])
            self.assert_clarification(result)
            inspect.assert_not_called()
            request.assert_not_called()
        self.assertIn("replace", self.resolve("Can I replace it?", history=[])[0]["clarifying_question"])

    def test_clarification_reply_preserves_previous_user_request(self):
        history = [{"question": "Can I replace it?", "retrieval_question": None,
                    "status": "needs_clarification", "text": "PRIVATE_ASSISTANT_CLARIFICATION"}]
        original = deepcopy(history)
        result, inspect, request = self.resolve("A physical SIM", history=history)
        self.assertEqual(result["retrieval_question"], "Can I replace a physical SIM?")
        self.assertIsNone(result["clarifying_question"])
        self.assertIsNone(result["usage"])
        self.assertEqual(history, original)
        inspect.assert_not_called()
        request.assert_not_called()

    def test_pending_reference_completion_keeps_negation_and_conditions(self):
        for previous, reply, expected in (
            ("Can I not replace it if damaged?", "A physical SIM",
             "Can I not replace a physical SIM if damaged?"),
            ("Can I return that?", "My phone", "Can I return my phone?"),
            ("Cancel it", "My mobile plan", "Cancel my mobile plan"),
        ):
            with self.subTest(previous=previous):
                history = [{"question": previous, "retrieval_question": None}]
                result, inspect, request = self.resolve(reply, history=history)
                self.assertEqual(result["retrieval_question"], expected)
                inspect.assert_not_called()
                request.assert_not_called()

    def test_explicit_pending_reply_does_not_revive_older_topics(self):
        history = [
            {"question": "How do I enable roaming?", "retrieval_question": "How do I enable roaming?"},
            {"question": "Can I return my phone?", "retrieval_question": "Can I return my phone?"},
            {"question": "Can I replace it?", "retrieval_question": None},
        ]
        result, _, request = self.resolve("A physical SIM", history=history)
        self.assertEqual(result["retrieval_question"], "Can I replace a physical SIM?")
        request.assert_not_called()

    def test_pending_reference_completion_obeys_history_and_question_limits(self):
        history = [{"question": "Can I replace it?", "retrieval_question": None}]
        for key, value in (("max_history_turns", 0), ("max_history_characters", 1)):
            settings = deepcopy(self.settings)
            settings["conversation"][key] = value
            result, inspect, request = self.resolve("A physical SIM", history=history, settings=settings)
            self.assert_clarification(result)
            inspect.assert_not_called()
            request.assert_not_called()
        # Each individual message fits; their combined retrieval question does not.
        settings = deepcopy(self.settings)
        settings["conversation"]["max_question_characters"] = 20
        result, _, _ = self.resolve("A physical SIM", history=history, settings=settings,
            response=self.response("Can I replace a physical SIM?"))
        self.assert_clarification(result)

    def test_complex_clarification_reply_still_requires_validated_rewrite(self):
        history = [{"question": "Can I replace it?", "retrieval_question": None,
                    "status": "needs_clarification", "text": "PRIVATE_ASSISTANT_CLARIFICATION"}]
        result, inspect, request = self.resolve("A damaged physical SIM", history=history,
            response=self.response("Can I replace a damaged physical SIM?"))
        self.assertEqual(result["retrieval_question"], "Can I replace a damaged physical SIM?")
        inspect.assert_called_once()
        self.assertNotIn("PRIVATE", json.dumps(request.call_args.args[2]))
        # An answer that omits the user's original action is not accepted.
        result, _, _ = self.resolve("A damaged physical SIM", history=history, response=self.response(
            "Can I book a damaged physical SIM?"))
        self.assert_clarification(result)

    def test_pending_reply_does_not_guess_person_or_multiple_references(self):
        for previous in ("Can she replace it?", "Can I replace it with that?", "What about it?"):
            with self.subTest(previous=previous):
                history = [{"question": previous, "retrieval_question": None}]
                response = self.response()
                response["message"]["content"] = json.dumps({
                    "status": "clarify", "retrieval_question": None, "history_turn": None})
                result, inspect, request = self.resolve("A physical SIM", history=history, response=response)
                self.assert_clarification(result)
                inspect.assert_called_once()
                request.assert_called_once()

    def test_topic_alone_needs_a_question_without_pending_clarification(self):
        for history in ([], self.history):
            for question in ("SIM", "A physical SIM", "Bill waiver", "Plan change", "Device return",
                             "Account transfer", "SIM replacement", "An appointment"):
                with self.subTest(question=question, pending=bool(history)):
                    result, inspect, request = self.resolve(question, history=history)
                    self.assert_clarification(result)
                    inspect.assert_not_called()
                    request.assert_not_called()

    def test_valid_follow_up_uses_only_user_questions_and_same_local_model(self):
        result, inspect, request = self.resolve()
        self.assertEqual(result["question"], self.question)
        self.assertEqual(result["retrieval_question"], self.rewritten)
        self.assertIsNone(result["clarifying_question"])
        self.assertEqual(result["usage"]["prompt_tokens"], 100)
        payload = request.call_args.args[2]
        self.assertEqual(payload["model"], self.settings["generation"]["model"])
        self.assertEqual(request.call_args.args[1], "/api/chat")
        self.assertFalse(payload["stream"])
        self.assertFalse(payload["think"])
        self.assertFalse(payload["format"]["additionalProperties"])
        self.assertNotIn("PRIVATE", json.dumps(payload))
        supplied = json.loads(payload["messages"][1]["content"])
        self.assertEqual(set(supplied["previous_user_questions"][0]), {"question", "retrieval_question"})
        inspect.assert_called_once()

    def test_named_topic_follow_up_preserves_prior_question_intent(self):
        for question in ("What about eSIM?", "How about eSIM?"):
            rewritten = "Do I need an appointment for an eSIM replacement?"
            result, inspect, request = self.resolve(question, response=self.response(rewritten))
            self.assertEqual(result["retrieval_question"], rewritten)
            self.assertIsNone(result["clarifying_question"])
            inspect.assert_called_once()
            supplied = json.loads(request.call_args.args[2]["messages"][1]["content"])
            self.assertEqual(supplied["current_question"], question)
            self.assertEqual(supplied["previous_user_questions"][0]["question"], self.previous)
        # Without a prior question there is no intent to carry into the new topic.
        result, _, request = self.resolve("What about eSIM?", history=[])
        self.assert_clarification(result)
        request.assert_not_called()

    def test_only_latest_three_user_turns_are_supplied(self):
        history = [{"question": "PRIVATE_EXPIRED_QUESTION", "retrieval_question": "PRIVATE_EXPIRED_QUESTION"}]
        history += deepcopy(self.history) * 3
        _, _, request = self.resolve(history=history)
        user_data = json.loads(request.call_args.args[2]["messages"][1]["content"])
        self.assertEqual(len(user_data["previous_user_questions"]), 3)
        self.assertNotIn("PRIVATE", json.dumps(user_data))

    def test_expired_topic_is_not_revived_to_resolve_pronoun(self):
        history = self.history + [{"question": "Thanks", "retrieval_question": "Thanks"}] * 3
        response = self.response()
        result, _, request = self.resolve("Can I replace it?", history=history, response=response)
        self.assert_clarification(result)
        self.assertNotIn(self.previous, request.call_args.args[2]["messages"][1]["content"])

    def test_new_chat_reset_has_no_old_referent(self):
        resolved, _, _ = self.resolve()
        self.assertEqual(resolved["retrieval_question"], self.rewritten)
        result, _, request = self.resolve(history=[])
        self.assert_clarification(result)
        request.assert_not_called()

    def test_multiple_topics_clarify_before_model(self):
        for history in (
            self.history + [{"question": "How do I enable roaming?", "retrieval_question": "How do I enable roaming?"}],
            [{"question": "Can I replace my SIM and phone?", "retrieval_question": "Can I replace my SIM and phone?"}],
        ):
            result, inspect, request = self.resolve("Can I replace it?", history=history)
            self.assert_clarification(result)
            inspect.assert_not_called()
            request.assert_not_called()

    def test_character_budget_keeps_whole_turns_and_never_reaches_across_a_gap(self):
        settings = deepcopy(self.settings)
        settings["conversation"]["max_history_characters"] = len(self.previous) * 2
        _, _, request = self.resolve(history=self.history * 3, settings=settings)
        data = json.loads(request.call_args.args[2]["messages"][1]["content"])
        self.assertEqual(len(data["previous_user_questions"]), 1)
        for history in (self.history + [{"question": "x" * 1001}], self.history + [None]):
            result, _, request = self.resolve(history=history, settings=settings)
            self.assert_clarification(result)
            request.assert_not_called()

    def test_disabled_or_too_small_memory_clarifies_without_call(self):
        for key, value in (("max_history_turns", 0), ("max_history_characters", 1)):
            settings = deepcopy(self.settings)
            settings["conversation"][key] = value
            result, _, request = self.resolve(settings=settings)
            self.assert_clarification(result)
            request.assert_not_called()

    def test_invalid_inputs_and_limits_have_safe_errors(self):
        for question, history in (("", []), (None, []), ("x" * 1001, []), ("A question", {})):
            with self.assertRaises(conversation.ConversationError):
                conversation.resolve_question(question, history, self.settings)
        for key, value in (("max_history_turns", True), ("max_history_turns", 11),
                           ("max_question_characters", 0), ("max_history_characters", -1)):
            settings = deepcopy(self.settings)
            settings["conversation"][key] = value
            with self.assertRaises(conversation.ConversationError):
                conversation.resolve_question(self.question, self.history, settings)

    def test_malformed_model_results_clarify_without_raw_content(self):
        malformed = ["PRIVATE_PROVIDER_BODY", "```json\n{}\n```", "[]",
                     '{"status":"resolved","status":"clarify"}',
                     json.dumps({"status": "resolved", "retrieval_question": self.rewritten,
                                 "history_turn": 0, "extra": "PRIVATE_EXTRA"}),
                     json.dumps({"status": "resolved", "retrieval_question": self.rewritten, "history_turn": True}),
                     json.dumps({"status": "resolved", "retrieval_question": self.rewritten, "history_turn": 99}),
                     json.dumps({"status": "clarify", "retrieval_question": None, "history_turn": None})]
        for raw in malformed:
            response = self.response()
            response["message"]["content"] = raw
            result, _, _ = self.resolve(response=response)
            self.assert_clarification(result)

    def test_refuses_new_facts_dropped_conditions_and_unresolved_pronouns(self):
        for rewritten in ("Can I book a free appointment for a physical SIM replacement anyway?",
                          "Do I need an appointment for a physical SIM replacement?",
                          "Can I book one anyway?", "<think>PRIVATE_THINKING</think>",
                          "Can I book an appointment for a physical SIM replacement?\nPRIVATE_EXTRA"):
            result, _, _ = self.resolve(response=self.response(rewritten))
            self.assert_clarification(result)
        result, _, _ = self.resolve("Can I not book one?", response=self.response(
            "Can I book an appointment for a physical SIM replacement?"))
        self.assert_clarification(result)

    def test_unexpected_model_thinking_tools_and_truncation_clarify(self):
        for updates in ({"done": False}, {"done_reason": "length"}, {"model": "unexpected"},
                        {"eval_count": self.settings["generation"]["num_predict"]},
                        {"prompt_eval_count": True}, {"eval_count": -1}):
            result, _, _ = self.resolve(response=self.response(**updates))
            self.assert_clarification(result)
        for key, value in (("thinking", "PRIVATE_THINKING"), ("tool_calls", ["PRIVATE_TOOL"]), ("role", "user")):
            response = self.response()
            response["message"][key] = value
            result, _, _ = self.resolve(response=response)
            self.assert_clarification(result)

    def test_model_unavailable_falls_back_without_exception_details(self):
        with patch.object(conversation, "inspect_model", side_effect=ValueError("PRIVATE_PROVIDER_ERROR")):
            self.assert_clarification(conversation.resolve_question(self.question, self.history, self.settings))

    def test_question_and_history_are_not_mutated(self):
        original = deepcopy(self.history)
        self.resolve()
        self.assertEqual(self.history, original)


class OwnActionQuestionTests(unittest.TestCase):
    def test_clear_policy_questions_about_the_user_are_recognised(self):
        for question in ("Can I book an appointment for a SIM replacement anyway?",
                         "Could I replace my physical SIM?", "May I collect my order?"):
            with self.subTest(question=question):
                self.assertTrue(conversation.asks_about_own_action(question))

    def test_direct_mixed_quoted_and_unnamed_requests_are_not_relabelled(self):
        for question in (None, "Can I book one anyway?", "Can you book a SIM appointment?",
                         "Can I ask you to waive my bill?", 'A colleague asked "Can I replace my SIM?"',
                         "Can I book an appointment, and waive my bill now?",
                         "Can I replace my SIM? Activate my service now."):
            with self.subTest(question=question):
                self.assertFalse(conversation.asks_about_own_action(question))


if __name__ == "__main__":
    unittest.main()
