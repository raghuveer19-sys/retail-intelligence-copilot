"""Offline chat integration checks; provider replies are simulated, not quality scores."""

from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from pinecone import Document

import test_answering as answering_fixtures
from retail_copilot import conversation, generate, pipeline, retrieve


APPOINTMENTS = "SIM-1024-v2:appointments:section-v1"
CHECKS = "SIM-1024-v2:checks:section-v1"
PLAN = "PLAN-1001-v1:allowances:section-v1"


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = answering_fixtures.AnsweringTests
        fixture.setUpClass()
        cls.base_settings = deepcopy(fixture.settings)
        cls.prepared = deepcopy(fixture.prepared)

    def setUp(self):
        self.settings = deepcopy(self.base_settings)
        # Existing contract tests also cover the retained model-draft lesson.
        self.settings["answering"]["presentation"] = "model_draft"
        self.question = "Do I need an appointment for a physical SIM replacement?"
        self.draft = {"status": "supported", "claims": [{
            "text": "A physical SIM replacement does not require an appointment.", "source_ids": ["S1"],
        }], "clarifying_question": None}
        self.records = {doc["_id"]: {key: deepcopy(value) for key, value in doc.items() if key != "embedding"}
                        for doc in self.prepared["documents"]}
        self.index = MagicMock()
        self.index.documents.search.return_value = self.search_response([APPOINTMENTS])
        self.index.documents.fetch.side_effect = lambda **kwargs: SimpleNamespace(
            namespace=self.settings["retrieval"]["namespace"], usage=SimpleNamespace(read_units=1),
            documents={identifier: Document(deepcopy(self.records[identifier])) for identifier in kwargs["ids"]},
        )
        self.client = MagicMock()
        self.client.indexes.describe.return_value = SimpleNamespace(host="offline.example")
        self.client.index.return_value.__enter__.return_value = self.index
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.prepare = self.stack.enter_context(patch.object(pipeline, "prepare_upload", return_value=self.prepared))
        self.credential = self.stack.enter_context(patch.object(pipeline, "read_credential", return_value="offline-key-only"))
        self.connection = self.stack.enter_context(patch.object(pipeline, "Pinecone"))
        self.connection.return_value.__enter__.return_value = self.client
        self.check_index = self.stack.enter_context(patch.object(pipeline, "check_index"))
        self.resolve = self.stack.enter_context(patch.object(pipeline, "resolve_question", side_effect=lambda question, history, settings: {
            "question": question, "retrieval_question": question, "clarifying_question": None, "usage": None,
        }))
        self.embed = self.stack.enter_context(patch.object(retrieve, "embed_local_query", side_effect=lambda question, *args: {
            "vector": [0.1] * 768, "embedding_input": "task: search result | query: " + question, "prompt_tokens": 20,
        }))
        self.inspect = self.stack.enter_context(patch.object(generate, "inspect_model", return_value={
            "digest": "d" * 64, "maximum_context_tokens": 262144, "think": False,
            "tokenizer": "gpt2", "template_sha256": "e" * 64,
        }))
        self.model_request = self.stack.enter_context(patch.object(generate, "request_local_json", side_effect=lambda *args: {
            "model": self.settings["generation"]["model"], "done": True, "done_reason": "stop",
            "message": {"role": "assistant", "content": json.dumps(self.draft)},
            "prompt_eval_count": 1000, "eval_count": 100, "total_duration": 1_000_000_000,
            "unrelated": "PRIVATE_PROVIDER_SENTINEL",
        }))
        self.stack.enter_context(patch("socket.socket.connect", side_effect=AssertionError("Network forbidden in offline tests")))

    def search_response(self, ids):
        return SimpleNamespace(
            namespace=self.settings["retrieval"]["namespace"], usage=SimpleNamespace(read_units=1),
            matches=[Document({**deepcopy(self.records[identifier]), "_score": 0.7}) for identifier in ids],
        )

    def run_turn(self, question=None, history=None):
        return pipeline.run_chat_turn(self.question if question is None else question,
                                      [] if history is None else history, self.settings)

    def assert_colleague_error(self, error):
        text = str(error).lower()
        for forbidden in ("ollama", "pinecone", "api key", "api_key", ".env", "config", "model",
                          "project", "file", "folder", "markdown", "prompt", "c:\\", "private_", "secret_provider"):
            self.assertNotIn(forbidden, text)

    def test_fresh_question_connects_existing_stages_and_keeps_sources_private(self):
        result = self.run_turn()
        self.assertEqual(result["question"], self.question)
        self.assertEqual(result["retrieval_question"], self.question)
        self.assertEqual(result["status"], "supported")
        self.assertEqual(result["text"], self.draft["claims"][0]["text"])
        self.assertNotIn("S1", result["text"])
        self.assertEqual(result["diagnostics"]["citations"][0]["source_file"], "SIM-1024-v2.json")
        self.assertEqual(result["diagnostics"]["generation"]["usage"]["prompt_tokens"], 1000)
        self.assertFalse(result["diagnostics"]["generation"]["claim_support_checked"])
        self.assertEqual(result["diagnostics"]["generation"]["claim_review_status"], "pending")
        self.assertNotIn("PRIVATE_PROVIDER_SENTINEL", json.dumps(result))
        self.check_index.assert_called_once()
        self.index.documents.search.assert_called_once()
        self.index.documents.upsert.assert_not_called()

    def test_each_turn_searches_and_generates_afresh_without_reusing_previous_answer(self):
        first = self.run_turn()
        self.draft["claims"][0]["text"] = "An optional booking may help plan a visit."
        second = self.run_turn("Is booking optional for a physical SIM replacement?", [first])
        self.assertNotEqual(first["text"], second["text"])
        self.assertEqual(self.index.documents.search.call_count, 2)
        self.assertEqual(self.model_request.call_count, 2)
        self.assertEqual(self.embed.call_args.args[0], second["question"])

    def test_source_passages_replace_model_paraphrase_and_keep_original_for_review(self):
        self.settings["answering"]["presentation"] = "source_passages"
        self.index.documents.search.return_value = self.search_response([APPOINTMENTS, CHECKS])
        self.draft["claims"][0]["text"] = "Identity verification is never needed."
        before = deepcopy(self.settings)
        result = self.run_turn()
        trace = result["diagnostics"]["generation"]
        self.assertNotIn("Identity verification is never needed.", result["text"])
        self.assertIn(self.records[APPOINTMENTS]["text"], result["text"])
        self.assertIn(self.records[CHECKS]["text"], result["text"])
        self.assertEqual(trace["model_draft"], self.draft)
        self.assertTrue(trace["source_assembly"]["exact_source_text_verified"])
        self.assertFalse(trace["claim_support_checked"])
        self.assertEqual(self.settings, before)

    def test_source_passages_action_boundary_and_missing_evidence_remain_explicit(self):
        self.settings["answering"]["presentation"] = "source_passages"
        action = self.run_turn("Replace this SIM now.")
        self.assertEqual(action["status"], "action_not_supported")
        self.assertIn("cannot perform the requested action", action["text"])
        self.draft["status"] = "insufficient_evidence"
        result = self.run_turn()
        self.assertIn("Here is the available policy guidance", result["text"])
        self.assertNotIn("don't have enough evidence to confirm every part", result["text"])
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertFalse(result["diagnostics"]["generation"]["model_coverage_status_verified"])
        self.assertIn(self.records[APPOINTMENTS]["text"], result["text"])
        self.draft["claims"] = []
        empty = self.run_turn()
        self.assertEqual(empty["text"], pipeline.STATUS_MESSAGES["insufficient_evidence"])
        self.assertEqual(empty["diagnostics"]["citations"], [])

    def test_missing_referenced_guidance_is_named_without_inventing_permission(self):
        draft = deepcopy(self.draft)
        draft["status"] = "insufficient_evidence"
        text = pipeline._natural_text(draft, "source_passages", {
            "referenced_policy_ids_without_passages": ["AUTH-1001", "IDV-1001"],
        })
        self.assertIn("AUTH-1001, IDV-1001", text)
        self.assertIn("can't confirm those requirements", text)
        self.assertIn(draft["claims"][0]["text"], text)
        self.assertNotIn("permission is granted", text)
        self.assertNotIn("prohibited", text)

    def test_own_booking_question_is_guidance_despite_model_action_label(self):
        self.settings["answering"]["presentation"] = "source_passages"
        self.draft["status"] = "action_not_supported"
        result = self.run_turn("Can I book an appointment for a physical SIM replacement anyway?")
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertNotIn("requested action", result["text"])
        self.assertIn(self.records[APPOINTMENTS]["text"], result["text"])
        trace = result["diagnostics"]["generation"]
        self.assertEqual(trace["model_draft"]["status"], "action_not_supported")
        self.assertTrue(trace["guidance_guard"]["status_changed"])
        self.assertFalse(trace["capability_guard"]["execution_requested"])
        self.assertFalse(trace["model_coverage_status_verified"])

    def test_own_question_mixed_with_execution_keeps_action_boundary(self):
        self.settings["answering"]["presentation"] = "source_passages"
        for question in ("Can you book an appointment for a SIM replacement?",
                         "Can I book a SIM appointment, and waive my outstanding bill now?"):
            with self.subTest(question=question):
                result = self.run_turn(question)
                self.assertEqual(result["status"], "action_not_supported")
                self.assertIn("cannot perform the requested action", result["text"])
                self.assertFalse(result["diagnostics"]["generation"]["guidance_guard"]["status_changed"])

    def test_follow_up_uses_resolved_question_but_never_previous_assistant_as_evidence(self):
        history = [{"question": self.question, "retrieval_question": self.question,
                    "text": "PRIVATE_ASSISTANT_SENTINEL", "diagnostics": {"text": "UNTRUSTED_EVIDENCE"}}]
        before = deepcopy(history)
        resolved = "Is an optional appointment available for physical SIM replacement?"
        self.resolve.side_effect = None
        self.resolve.return_value = {"question": "Can I book one anyway?", "retrieval_question": resolved,
                                     "clarifying_question": None, "usage": {"prompt_tokens": 50}}
        result = self.run_turn("Can I book one anyway?", history)
        self.assertEqual(self.resolve.call_args.args[1], [{"question": self.question, "retrieval_question": self.question}])
        self.assertEqual(self.embed.call_args.args[0], resolved)
        model_messages = self.model_request.call_args.args[2]["messages"]
        self.assertEqual(json.loads(model_messages[1]["content"])["question"], resolved)
        self.assertNotIn("PRIVATE_ASSISTANT_SENTINEL", json.dumps(model_messages))
        self.assertNotIn("UNTRUSTED_EVIDENCE", json.dumps(model_messages))
        self.assertEqual(history, before)
        self.assertEqual(result["question"], "Can I book one anyway?")
        self.assertTrue(result["diagnostics"]["retrieval"]["query_rewritten"])
        self.assertEqual(result["diagnostics"]["retrieval"]["user_question"], "Can I book one anyway?")

    def test_clarification_has_no_corpus_credentials_pinecone_or_generation_calls(self):
        self.resolve.side_effect = None
        self.resolve.return_value = {"question": "Can I replace it?", "retrieval_question": None,
                                     "clarifying_question": "What would you like to replace?", "usage": None}
        result = self.run_turn("Can I replace it?")
        self.assertEqual(result["text"], "What would you like to replace?")
        self.assertEqual(result["status"], "needs_clarification")
        self.assertEqual(result["diagnostics"]["citations"], [])
        for mocked in (self.prepare, self.credential, self.connection, self.embed, self.inspect, self.model_request):
            mocked.assert_not_called()

    def test_acknowledgements_reply_without_resolution_evidence_or_service_calls(self):
        history = [{"question": self.question, "retrieval_question": self.question,
                    "text": "PRIVATE_ASSISTANT_TEXT", "diagnostics": {"private": "PRIVATE_TRACE"}}]
        before = deepcopy(history)
        for question in ("Thanks", "OK thanks", "Okay", "Thank you!"):
            with self.subTest(question=question):
                result = self.run_turn(question, history)
                self.assertEqual(result["status"], "acknowledgement")
                self.assertEqual(result["question"], question)
                self.assertTrue(result["text"].strip())
                self.assertIsNone(result["retrieval_question"])
                self.assertFalse(result["diagnostics"]["model_call_made"])
                self.assertEqual(result["diagnostics"]["service_calls_made"], 0)
                for field in ("resolution", "retrieval", "context", "generation"):
                    self.assertIsNone(result["diagnostics"][field])
                self.assertEqual(result["diagnostics"]["citations"], [])
                self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertEqual(history, before)
        for mocked in (self.resolve, self.prepare, self.credential, self.connection,
                       self.embed, self.inspect, self.model_request):
            mocked.assert_not_called()

    def test_acknowledgements_still_enforce_input_and_conversation_limits(self):
        for key, value in (("max_question_characters", 0), ("max_history_turns", 11),
                           ("max_history_characters", -1)):
            with self.subTest(limit=key):
                self.settings = deepcopy(self.base_settings)
                self.settings["conversation"][key] = value
                with self.assertRaises(pipeline.ChatError) as caught:
                    self.run_turn("Thanks")
                self.assert_colleague_error(caught.exception)
        self.settings = deepcopy(self.base_settings)
        self.settings["conversation"]["max_question_characters"] = 20
        with patch.object(pipeline, "acknowledgement_reply") as reply, self.assertRaisesRegex(pipeline.ChatError, "shorten"):
            self.run_turn("Thanks " + "!" * 20)
        reply.assert_not_called()
        with self.assertRaises(pipeline.ChatError):
            pipeline.run_chat_turn("Thanks", "invalid history", self.settings)
        for mocked in (self.resolve, self.prepare, self.credential, self.connection, self.model_request):
            mocked.assert_not_called()

    def test_mixed_thanks_and_policy_question_use_normal_pipeline(self):
        question = "OK thanks, can I replace my SIM?"
        result = self.run_turn(question)
        self.assertEqual(result["status"], "supported")
        self.resolve.assert_called_once()
        self.assertEqual(self.resolve.call_args.args[0], question)
        self.index.documents.search.assert_called_once()
        self.model_request.assert_called_once()

    def test_yes_without_a_clear_referent_clarifies_instead_of_acknowledging(self):
        self.resolve.side_effect = conversation.resolve_question
        result = self.run_turn("Yes")
        self.assertEqual(result["status"], "needs_clarification")
        self.assertIsNone(result["retrieval_question"])
        self.resolve.assert_called_once()
        self.connection.assert_not_called()
        self.model_request.assert_not_called()

    def test_direct_pipeline_history_excludes_acknowledgements_without_mutating_it(self):
        previous = {"question": self.question, "retrieval_question": self.question, "status": "supported"}
        acknowledgement = {"question": "Thanks", "retrieval_question": None,
                           "status": "acknowledgement", "text": "You're welcome!"}
        history = [previous, acknowledgement]
        before = deepcopy(history)
        self.run_turn("Can I book one anyway?", history)
        self.assertEqual(self.resolve.call_args.args[1], [{"question": self.question, "retrieval_question": self.question}])
        self.assertEqual(history, before)

    def test_skipped_acknowledgements_never_revive_expired_or_failed_topics(self):
        previous = {"question": self.question, "retrieval_question": self.question, "status": "supported"}
        acknowledgement = {"question": "Thanks", "retrieval_question": None, "status": "acknowledgement"}
        failure = {"question": "What about roaming?", "retrieval_question": None, "status": "error"}
        self.resolve.side_effect = conversation.resolve_question
        for history in ([previous, acknowledgement, acknowledgement, acknowledgement],
                        [previous, failure, acknowledgement]):
            with self.subTest(history=history):
                result = self.run_turn("Can I book one anyway?", history)
                self.assertEqual(self.resolve.call_args.args[1], [])
                self.assertEqual(result["status"], "needs_clarification")
        self.prepare.assert_not_called()
        self.connection.assert_not_called()
        self.model_request.assert_not_called()

    def test_no_evidence_uses_fixed_fallback_without_answer_model(self):
        self.index.documents.search.return_value = self.search_response([])
        result = self.run_turn()
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertIn("could not find enough approved evidence", result["text"])
        self.assertEqual(result["diagnostics"]["citations"], [])
        self.inspect.assert_not_called()
        self.model_request.assert_not_called()

    def test_policy_lookup_is_bounded_once_and_fetched_sources_have_no_invented_score(self):
        self.index.documents.search.return_value = self.search_response([CHECKS])
        result = self.run_turn("What checks apply to a physical SIM replacement?")
        self.index.documents.fetch.assert_called_once()
        lookup = result["diagnostics"]["retrieval"]["policy_lookup"]
        self.assertLessEqual(lookup["added_chunks"], self.settings["policy_lookup"]["max_added_chunks"])
        self.assertLessEqual(len(lookup["policy_ids"]), self.settings["policy_lookup"]["max_policies"])
        fetched = [entry for entry in result["diagnostics"]["context"]["source_registry"].values()
                   if entry["retrieval_method"] == "policy_lookup"]
        self.assertTrue(fetched)
        self.assertTrue(all(entry["similarity_score"] is None for entry in fetched))

    def test_invalid_source_label_rejects_entire_answer(self):
        self.draft["claims"][0]["source_ids"] = ["S99"]
        with self.assertRaises(pipeline.ChatError) as caught:
            self.run_turn()
        self.assertNotIn("S99", str(caught.exception))

    def test_changed_pinecone_passage_stops_before_generation(self):
        self.index.documents.search.return_value.matches[0] = Document({
            **self.records[APPOINTMENTS], "text": "Changed source text", "_score": 0.7,
        })
        with self.assertRaises(pipeline.ChatError):
            self.run_turn()
        self.model_request.assert_not_called()

    def test_context_revalidated_before_generation(self):
        original = pipeline.build_context
        def tampered(*args):
            pack = original(*args)
            pack["source_registry"]["S1"]["metadata"]["source_file"] = "wrong.json"
            return pack
        with patch.object(pipeline, "build_context", side_effect=tampered), self.assertRaises(pipeline.ChatError):
            self.run_turn()
        self.model_request.assert_not_called()

    def test_provider_failure_is_safe_and_does_not_return_stale_answer(self):
        first = self.run_turn()
        self.index.documents.search.side_effect = RuntimeError("SECRET_PROVIDER_KEY_AND_BODY")
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(pipeline.ChatError) as caught:
            self.run_turn("Another question", [first])
        self.assertNotIn("SECRET_PROVIDER", str(caught.exception) + output.getvalue())
        self.assertNotIn(first["text"], str(caught.exception))
        self.assert_colleague_error(caught.exception)
        self.assertIn("try again", str(caught.exception))
        self.assertIn("copilot support", str(caught.exception))
        self.assertEqual(self.model_request.call_count, 1)

    def test_unknown_index_corpus_is_rejected_before_any_search(self):
        self.check_index.side_effect = ValueError("corpus does not match")
        with self.assertRaises(pipeline.ChatError):
            self.run_turn()
        self.index.documents.search.assert_not_called()

    def test_missing_key_is_safe_and_does_not_connect(self):
        self.credential.return_value = ""
        with self.assertRaisesRegex(pipeline.ChatError, "copilot support") as caught:
            self.run_turn()
        self.assert_colleague_error(caught.exception)
        self.connection.assert_not_called()

    def test_generation_service_failure_stays_an_error_without_developer_details(self):
        self.model_request.side_effect = RuntimeError("Ollama PRIVATE_MODEL_DETAILS C:\\private\\.env SECRET_PROVIDER_KEY")
        with self.assertRaises(pipeline.ChatError) as caught:
            self.run_turn()
        self.assert_colleague_error(caught.exception)
        self.assertIn("couldn't complete this reply", str(caught.exception))
        self.assertIn("copilot support", str(caught.exception))

    def test_invalid_configuration_hides_paths_and_directs_to_copilot_support(self):
        for section, key, value in (("retrieval", "request_timeout_seconds", -1),
                                    ("answering", "system_prompt_file", "data/PRIVATE_INSTRUCTIONS.md")):
            with self.subTest(section=section):
                self.settings = deepcopy(self.base_settings)
                self.settings[section][key] = value
                with self.assertRaises(pipeline.ChatError) as caught:
                    self.run_turn()
                self.assert_colleague_error(caught.exception)
                self.assertIn("copilot support", str(caught.exception))
        self.connection.assert_not_called()

    def test_settings_load_failure_is_not_reported_as_a_bad_user_question(self):
        with patch.object(pipeline, "load_settings", side_effect=OSError("PRIVATE_SETTINGS C:\\private\\config.toml")), \
                self.assertRaises(pipeline.ChatError) as caught:
            pipeline.run_chat_turn(self.question, [])
        self.assert_colleague_error(caught.exception)
        self.assertIn("copilot support", str(caught.exception))
        self.assertNotIn("understand that question", str(caught.exception))
        self.resolve.assert_not_called()

    def test_missing_evidence_is_distinct_from_service_failure(self):
        self.index.documents.search.return_value = self.search_response([])
        insufficient = self.run_turn()
        self.index.documents.search.side_effect = RuntimeError("PRIVATE_PROVIDER_FAILURE")
        with self.assertRaises(pipeline.ChatError) as caught:
            self.run_turn()
        self.assertEqual(insufficient["status"], "insufficient_evidence")
        self.assertIn("policy owner", insufficient["text"])
        self.assertIn("could not find enough approved evidence", insufficient["text"])
        self.assertNotIn("could not find enough approved evidence", str(caught.exception))
        self.assert_colleague_error(caught.exception)

    def test_question_is_not_saved_and_no_saved_answer_is_read(self):
        read = Path.read_text
        paths = []
        def traced_read(path, *args, **kwargs):
            paths.append(path)
            return read(path, *args, **kwargs)
        with patch.object(Path, "read_text", traced_read), patch.object(
            Path, "write_text", side_effect=AssertionError("No disk writes")), patch.object(
            Path, "write_bytes", side_effect=AssertionError("No disk writes")), patch(
            "retail_copilot.prepare_chunks.save_chunk_export", side_effect=AssertionError("No saved chat artifacts")), patch(
            "builtins.print", side_effect=AssertionError("No question or answer logging")):
            self.run_turn()
        self.assertEqual(paths, [(pipeline.PROJECT_ROOT / self.settings["answering"]["system_prompt_file"]).resolve()])

    def test_generated_clarification_has_no_technical_prefix_or_citations(self):
        self.draft = {"status": "needs_clarification", "claims": [],
                      "clarifying_question": "Do you mean a physical SIM or an eSIM?"}
        result = self.run_turn()
        self.assertEqual(result["text"], self.draft["clarifying_question"])
        self.assertEqual(result["diagnostics"]["citations"], [])

    def test_action_limit_remains_visible_with_natural_policy_guidance(self):
        self.draft["status"] = "action_not_supported"
        result = self.run_turn()
        self.assertIn("cannot perform the requested action", result["text"])
        self.assertIn(self.draft["claims"][0]["text"], result["text"])
        self.assertNotIn("[S1]", result["text"])

    def test_explicit_action_boundary_is_enforced_independently_of_model_status(self):
        for question in ("Waive my outstanding bill now.",
                         "What is the return window, and can you refund my bill payment?"):
            for status in ("supported", "insufficient_evidence", "needs_clarification"):
                with self.subTest(question=question, status=status):
                    self.draft = {"status": status, "claims": [] if status == "needs_clarification" else [{
                        "text": "An optional booking may help plan a visit.", "source_ids": ["S1"]}],
                        "clarifying_question": "Which bill?" if status == "needs_clarification" else None}
                    before = deepcopy(self.draft)
                    result = self.run_turn(question)
                    trace = result["diagnostics"]["generation"]
                    self.assertEqual(result["status"], "action_not_supported")
                    self.assertIn("cannot perform the requested action", result["text"])
                    self.assertEqual(trace["model_draft"], before)
                    self.assertEqual(trace["draft"]["claims"], before["claims"])
                    self.assertIsNone(trace["draft"]["clarifying_question"])
                    self.assertTrue(trace["capability_guard"]["status_changed"])
                    self.assertFalse(trace["claim_support_checked"])
                    self.assertEqual(self.draft, before)

    def test_eligibility_questions_are_not_converted_to_execution_requests(self):
        for question in ("Can I replace my SIM?", "How do I request a refund?",
                         "Do not waive my bill; explain the policy."):
            with self.subTest(question=question):
                result = self.run_turn(question)
                self.assertEqual(result["status"], "supported")
                self.assertFalse(result["diagnostics"]["generation"]["capability_guard"]["execution_requested"])

    def test_action_without_evidence_refuses_execution_without_inventing_claims(self):
        self.index.documents.search.return_value = self.search_response([])
        result = self.run_turn("Waive my outstanding bill now.")
        self.assertEqual(result["status"], "action_not_supported")
        self.assertEqual(result["diagnostics"]["generation"]["draft"]["claims"], [])
        self.assertEqual(result["diagnostics"]["citations"], [])
        self.model_request.assert_not_called()

    def test_no_default_question_or_mutation_of_settings(self):
        original = deepcopy(self.settings)
        for question in ("", " ", None, 42):
            with self.subTest(question=question), self.assertRaises(pipeline.ChatError):
                pipeline.run_chat_turn(question, [], self.settings)
        self.resolve.assert_not_called()
        self.assertEqual(self.settings, original)

    def test_unexpected_thinking_or_malformed_content_is_rejected_not_cleaned_up(self):
        for message in ({"role": "assistant", "content": json.dumps(self.draft), "thinking": "PRIVATE_THINKING_SENTINEL"},
                        {"role": "assistant", "content": "<think>PRIVATE_THINKING_SENTINEL</think>" + json.dumps(self.draft)}):
            with self.subTest(message=message):
                self.model_request.side_effect = None
                self.model_request.return_value = {
                    "model": self.settings["generation"]["model"], "done": True, "done_reason": "stop",
                    "message": message, "prompt_eval_count": 1000, "eval_count": 100, "total_duration": 0,
                }
                with self.assertRaises(pipeline.ChatError) as caught:
                    self.run_turn()
                self.assertNotIn("PRIVATE_THINKING_SENTINEL", str(caught.exception))

    def test_display_plan_names_normalize_before_resolution_and_preserve_canonical_evidence(self):
        question = "Compare Connect Essential and Connect Plus allowances."
        canonical = "Compare Practice Basic and Practice Plus allowances."
        self.index.documents.search.return_value = self.search_response([PLAN])
        self.draft["claims"][0]["text"] = (
            "The fictional Practice Basic plan includes 10 GB per monthly cycle. "
            "Practice Plus includes 30 GB. No monthly prices are defined."
        )
        before = deepcopy(self.prepared)
        result = self.run_turn(question)
        self.assertEqual(self.resolve.call_args.args[0], canonical)
        self.assertEqual(self.embed.call_args.args[0], canonical)
        self.assertEqual(result["question"], question)
        self.assertEqual(result["retrieval_question"], canonical)
        self.assertEqual(result["diagnostics"]["original_question"], question)
        self.assertEqual(result["diagnostics"]["normalized_question"], canonical)
        self.assertTrue(result["diagnostics"]["plan_aliases_applied"])
        self.assertEqual(result["text"], "The Connect Essential plan includes 10 GB per monthly cycle. "
                         "Connect Plus includes 30 GB. No monthly prices are defined.")
        self.assertEqual(result["diagnostics"]["generation"]["draft"], self.draft)
        self.assertEqual(result["diagnostics"]["citations"][0]["source_file"], "PLAN-1001-v1.json")
        self.assertIn("Practice Basic", result["diagnostics"]["context"]["context_text"])
        self.assertNotIn("Connect Essential", result["diagnostics"]["context"]["context_text"])
        self.assertEqual(self.prepared, before)
        self.index.documents.upsert.assert_not_called()

    def test_plan_aliases_normalize_history_copies_and_preserve_unresolved_marker(self):
        history = [{"question": "How much data does Connect Essential include?",
                    "retrieval_question": "How much data does Practice Basic include?",
                    "text": "PRIVATE_ASSISTANT_TEXT"},
                   {"question": "Does Connect Plus have more?", "retrieval_question": None}]
        before = deepcopy(history)
        self.run_turn("What about Connect Plus?", history)
        self.assertEqual(self.resolve.call_args.args[0], "What about Practice Plus?")
        self.assertEqual(self.resolve.call_args.args[1], [
            {"question": "How much data does Practice Basic include?", "retrieval_question": "How much data does Practice Basic include?"},
            {"question": "Does Practice Plus have more?", "retrieval_question": None},
        ])
        self.assertEqual(history, before)

    def test_pre_retrieval_and_generated_clarifications_use_visible_plan_names(self):
        self.resolve.side_effect = None
        self.resolve.return_value = {"question": "Practice Basic", "retrieval_question": None,
                                     "clarifying_question": "What would you like to know about fictional Practice Basic?", "usage": None}
        result = self.run_turn("Connect Essential")
        self.assertEqual(result["text"], "What would you like to know about Connect Essential?")
        self.assertEqual(result["question"], "Connect Essential")
        self.assertEqual(result["diagnostics"]["normalized_question"], "Practice Basic")
        self.assertEqual(result["diagnostics"]["resolution"]["clarifying_question"],
                         "What would you like to know about fictional Practice Basic?")
        self.connection.assert_not_called()
        self.resolve.side_effect = lambda question, *args: {
            "question": question, "retrieval_question": question, "clarifying_question": None, "usage": None,
        }
        self.draft = {"status": "needs_clarification", "claims": [],
                      "clarifying_question": "Do you mean Practice Basic or Practice Plus?"}
        result = self.run_turn("Which plan has more data?")
        self.assertEqual(result["text"], "Do you mean Connect Essential or Connect Plus?")
        self.assertEqual(result["diagnostics"]["generation"]["draft"], self.draft)

    def test_short_display_name_reply_uses_real_resolver_with_canonical_user_terms(self):
        self.resolve.side_effect = conversation.resolve_question
        self.index.documents.search.return_value = self.search_response([PLAN])
        self.draft["claims"][0]["text"] = "Practice Basic includes 10 GB per monthly cycle."
        history = [{"question": "How much data does the plan include?", "retrieval_question": None}]
        response = {"model": self.settings["generation"]["model"], "done": True, "done_reason": "stop",
                    "message": {"role": "assistant", "content": json.dumps({
                        "status": "resolved", "retrieval_question": "How much data does the Practice Basic plan include?", "history_turn": 0})},
                    "prompt_eval_count": 100, "eval_count": 50}
        with patch.object(conversation, "inspect_model", return_value={"think": False}), patch.object(
            conversation, "request_local_json", return_value=response,
        ) as request:
            result = self.run_turn("Connect Essential", history)
        self.assertEqual(result["text"], "Connect Essential includes 10 GB per monthly cycle.")
        self.assertEqual(result["retrieval_question"], "How much data does the Practice Basic plan include?")
        supplied = json.loads(request.call_args.args[2]["messages"][1]["content"])
        self.assertEqual(supplied["current_question"], "Practice Basic")
        self.assertEqual(supplied["previous_user_questions"][0]["question"], history[0]["question"])

    def test_invalid_alias_configuration_stops_before_resolver_or_services(self):
        self.settings["plan_aliases"] = {"Practice Basic": "Connect", "Practice Plus": "connect"}
        with self.assertRaises(pipeline.ChatError) as caught:
            self.run_turn()
        self.assert_colleague_error(caught.exception)
        self.assertIn("copilot support", str(caught.exception))
        self.resolve.assert_not_called()
        self.connection.assert_not_called()


if __name__ == "__main__":
    unittest.main()
