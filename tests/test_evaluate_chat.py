"""Offline harness checks; simulated answers are not evidence of model quality."""

from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from retail_copilot import evaluate_chat
from retail_copilot.documents import PROJECT_ROOT, load_settings
from retail_copilot.pipeline import ChatError


class ChatEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name in ("data/processed", "evaluation", "prompts", "src/retail_copilot"):
            (self.root / name).mkdir(parents=True)
        self.settings = load_settings()
        self.settings["answering"]["system_prompt_file"] = "prompts/answering.md"
        self.cases = json.loads((PROJECT_ROOT / "evaluation/cases.json").read_text(encoding="utf-8"))
        (self.root / "evaluation/cases.json").write_text(json.dumps(self.cases), encoding="utf-8")
        (self.root / "prompts/answering.md").write_text("Answer from approved evidence.", encoding="utf-8")
        (self.root / "prompts/conversation.md").write_text("Resolve user references only.", encoding="utf-8")
        (self.root / "src/retail_copilot/pipeline.py").write_text("# source identity fixture\n", encoding="utf-8")
        self.prepared = {"documents": [{"_id": "fixture"}], "model_digest": "a" * 64,
                         "corpus_sha256": "b" * 64, "as_of_date": self.settings["demo"]["as_of_date"]}
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(evaluate_chat, "PROJECT_ROOT", self.root))
        self.stack.enter_context(patch.object(evaluate_chat, "load_settings", return_value=self.settings))
        self.prepare = self.stack.enter_context(patch.object(evaluate_chat, "prepare_upload", return_value=self.prepared))
        self.chat = self.stack.enter_context(patch.object(evaluate_chat, "run_chat_turn", side_effect=self.turn))
        self.stack.enter_context(patch("socket.socket.connect", side_effect=AssertionError("No network allowed")))

    def case(self, identifier="E01"):
        return deepcopy(next(case for case in self.cases if case["test_id"] == identifier))

    def turn(self, question, history, settings):
        if question == self.case("E07")["user_question"]:
            return {"question": question, "text": "What would you like to replace?", "status": "needs_clarification",
                    "retrieval_question": None, "diagnostics": {
                        "retrieval": None, "context": None, "generation": None, "citations": [],
                        "resolution": {"question": question, "retrieval_question": None, "usage": None},
                    }}
        metadata = {"document_id": "SIM-1024-v2", "section_id": "appointments", "source_file": "SIM-1024-v2.json"}
        return {"question": question, "text": "An appointment is optional.", "status": "supported", "retrieval_question": question,
                "diagnostics": {
                    "resolution": {"question": question, "retrieval_question": question, "usage": None},
                    "retrieval": {"matches": [{"chunk_id": "fixture", "text": "An appointment is not required.", "metadata": metadata}],
                                  "pinecone_read_units": 2, "query_prompt_tokens": 20},
                    "context": {"context_text": json.dumps({"question": question, "sources": [{"text": "An appointment is not required."}]}),
                                "source_registry": {"S1": {"chunk_id": "fixture", "metadata": metadata}}},
                    "generation": {"model_call_made": True, "source_ids_valid": True, "claim_support_checked": False,
                                   "model_digest": "d" * 64, "draft": {"claims": [{"text": "An appointment is optional.", "source_ids": ["S1"]}]},
                                   "usage": {"prompt_tokens": 1000, "generated_tokens_including_thinking": 100}},
                    "citations": [{"source_id": "S1", "chunk_id": "fixture", **metadata}],
                }}

    def execute(self, *args):
        output = io.StringIO()
        with redirect_stdout(output):
            code = evaluate_chat.main(list(args))
        return code, output.getvalue()

    def output(self, name="chat-evaluation-2026-10-18"):
        return self.root / "data/processed" / name

    def saved(self, name, folder=None):
        return json.loads(((folder or self.output()) / name).read_text(encoding="utf-8"))

    def test_preview_validates_locally_without_calls_or_writes(self):
        with patch.object(evaluate_chat, "write_new") as write:
            code, text = self.execute()
        self.assertEqual(code, 0)
        self.assertIn("PREVIEW ONLY", text)
        self.assertIn("E01, E05, E07, E08, E09", text)
        self.chat.assert_not_called()
        write.assert_not_called()
        self.assertFalse(self.output().exists())

    def test_current_pipeline_receives_only_question_empty_history_and_settings(self):
        code, _ = self.execute("--run")
        self.assertEqual(code, 0)
        calls = self.chat.call_args_list
        self.assertEqual(len(calls), 5)
        self.assertEqual([call.args[0] for call in calls], [self.case(identifier)["user_question"] for identifier in evaluate_chat.DEFAULT_CASES])
        self.assertTrue(all(call.args[1] == [] for call in calls))
        self.assertEqual(len({id(call.args[1]) for call in calls}), 5)
        for call in calls:
            self.assertEqual(call.args[2], self.settings)
            self.assertEqual(len(call.args), 3)
            self.assertEqual(call.kwargs, {})
            self.assertNotIn("must_include", json.dumps(call.args))
            self.assertNotIn("reference_answer", json.dumps(call.args))

    def test_success_preserves_exact_visible_answer_evidence_and_separate_expectations(self):
        question = self.case()["user_question"]
        expected = self.turn(question, [], self.settings)
        self.execute("--run", "--case", "E01")
        record = self.saved("E01.json")
        self.assertEqual(record["result"], expected)
        self.assertEqual(record["result_sha256"], evaluate_chat.fingerprint(expected))
        self.assertEqual(record["input"], {"question": question, "history": []})
        self.assertEqual(record["authored_expectations_not_sent_to_pipeline"]["must_include"], self.case()["must_include"])
        self.assertEqual(record["semantic_review"]["status"], "pending")
        self.assertIsNone(record["semantic_review"]["overall_pass"])
        self.assertTrue(record["automated_checks"]["source_ids_valid"])
        self.assertEqual(record["retrieval_review"]["expected_section_recall"], 1)
        self.assertEqual(self.saved("summary.json")["reviewed_cases"], 0)
        self.assertIsNone(self.saved("summary.json")["answer_quality_pass_rate"])

    def test_early_clarification_has_no_retrieval_or_source_check_score(self):
        self.execute("--run", "--case", "E07")
        record = self.saved("E07.json")
        self.assertEqual(record["result"]["status"], "needs_clarification")
        self.assertEqual(record["retrieval_review"]["scope"], "not_performed")
        self.assertIsNone(record["retrieval_review"]["expected_section_recall"])
        self.assertIsNone(record["automated_checks"]["source_ids_valid"])
        self.assertEqual(record["usage"]["pinecone_read_units"], 0)
        self.assertEqual(record["usage"]["query_embedding_input_tokens"], 0)
        self.assertEqual(record["usage"]["generation_input_tokens"], 0)
        self.assertIsNone(record["usage"]["resolution_input_tokens"])

    def test_failure_is_saved_once_without_raw_provider_details_and_others_continue(self):
        failed_question = self.case("E05")["user_question"]
        def attempt(question, history, settings):
            if question == failed_question:
                raise RuntimeError("PRIVATE_PROVIDER_BODY API_KEY=PRIVATE_KEY")
            return self.turn(question, history, settings)
        self.chat.side_effect = attempt
        code, output = self.execute("--run")
        self.assertEqual(code, 1)
        self.assertEqual(self.chat.call_count, 5)
        failed = self.saved("E05-failure.json")
        self.assertEqual(failed["artifact_type"], "chat_evaluation_failure")
        self.assertIsNone(failed["result"])
        self.assertIsNone(failed["failure"]["usage_for_failed_calls"])
        self.assertIsNone(failed["usage"]["pinecone_read_units"])
        self.assertGreaterEqual(failed["usage"]["elapsed_seconds"], 0)
        summary = self.saved("summary.json")
        self.assertEqual((summary["completed_cases"], summary["failed_cases"]), (4, 1))
        self.assertEqual(summary["usage"]["pinecone_read_units"]["reported_subtotal"], 6)
        self.assertIsNone(summary["usage"]["pinecone_read_units"]["complete_total"])
        self.assertEqual(summary["usage"]["pinecone_read_units"]["unknown_case_ids"], ["E05"])
        self.assertNotIn("PRIVATE", json.dumps(failed) + json.dumps(summary) + output)

    def test_authored_chat_errors_remain_failed_not_successful_fallbacks(self):
        self.chat.side_effect = ChatError("Please try again. If this continues, contact copilot support.")
        code, _ = self.execute("--run", "--case", "E01")
        self.assertEqual(code, 1)
        failed = self.saved("E01-failure.json")
        self.assertIn("copilot support", failed["failure"]["message"])
        self.assertEqual(failed["execution_status"], "failed")
        self.assertIsNone(failed["result"])
        self.assertFalse((self.output() / "E01.json").exists())

    def test_invalid_pipeline_result_is_failed_not_scored(self):
        self.chat.return_value = {"question": "wrong question", "text": "PRIVATE_REPLY", "status": "supported", "diagnostics": {}}
        self.chat.side_effect = None
        code, _ = self.execute("--run", "--case", "E01")
        self.assertEqual(code, 1)
        self.assertNotIn("PRIVATE_REPLY", json.dumps(self.saved("E01-failure.json")))

    def test_second_run_refuses_existing_results_before_any_call(self):
        self.execute("--run", "--case", "E01")
        before = {path.name: path.read_bytes() for path in self.output().iterdir()}
        self.chat.reset_mock()
        code, text = self.execute("--run", "--case", "E01")
        self.assertEqual(code, 1)
        self.assertIn("never overwritten or resumed", text)
        self.chat.assert_not_called()
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.output().iterdir()})

    def test_output_containment_and_unrelated_artifacts_are_protected(self):
        for name in ("data/processed", "../outside", str(self.root / "absolute"), "data/knowledge/run", "data/processed/nested/run", "data/processed/file.json"):
            with self.subTest(name=name), self.assertRaises(evaluate_chat.ChatEvaluationError):
                evaluate_chat.output_directory(self.root, name)
        folder = self.output("existing-results")
        folder.mkdir()
        artifact = folder / "unrelated.json"
        artifact.write_text("keep this", encoding="utf-8")
        with self.assertRaises(evaluate_chat.ChatEvaluationError):
            evaluate_chat.output_directory(self.root, "data/processed/existing-results")
        self.assertEqual(artifact.read_text(encoding="utf-8"), "keep this")
        with self.assertRaises(FileExistsError):
            evaluate_chat.write_new(artifact, {"replace": True})

    def test_case_selection_rejects_duplicates_unknown_and_controlled_case(self):
        for identifiers in (["E01", "E01"], ["E99"], ["E11"]):
            with self.subTest(identifiers=identifiers), self.assertRaises(evaluate_chat.ChatEvaluationError):
                evaluate_chat.selected_cases(self.root, self.settings, identifiers)
        self.execute("--run", "--case", "E09", "--case", "E07", "--output-dir", "data/processed/custom-run")
        self.assertEqual(self.saved("manifest.json", self.output("custom-run"))["case_ids"], ["E09", "E07"])

    def test_manifest_whitelists_settings_and_fingerprints_chat_inputs(self):
        self.settings["generation"]["api_key"] = "PRIVATE_KEY"
        self.settings["generation"]["api_base_url"] = "https://PRIVATE_ENDPOINT"
        self.settings["extra_secret"] = "PRIVATE_EXTRA"
        cases = evaluate_chat.selected_cases(self.root, self.settings, None)
        manifest = evaluate_chat.build_manifest(self.root, self.settings, cases, self.prepared)
        self.assertNotIn("PRIVATE", json.dumps(manifest))
        identity = manifest["identity"]
        self.assertEqual(identity["configuration"]["conversation"]["max_history_turns"], 3)
        self.assertEqual(identity["configuration"]["plan_aliases"], self.settings["plan_aliases"])
        self.assertIn("src/retail_copilot/pipeline.py", identity["input_file_sha256"])
        self.assertIn("prompts/conversation.md", identity["input_file_sha256"])
        self.assertIn("prompts/answering.md", identity["input_file_sha256"])
        self.assertIn("evaluation/cases.json", identity["input_file_sha256"])
        self.assertEqual(identity["corpus"]["corpus_sha256"], self.prepared["corpus_sha256"])
        for section, key, value in (("conversation", "max_history_turns", 2), ("plan_aliases", "Practice Basic", "Other Essential")):
            changed = deepcopy(self.settings)
            changed[section][key] = value
            after = evaluate_chat.build_manifest(self.root, changed, cases, self.prepared)
            self.assertNotEqual(after["identity_sha256"], manifest["identity_sha256"])
        (self.root / "prompts/conversation.md").write_text("Changed instructions.", encoding="utf-8")
        after = evaluate_chat.build_manifest(self.root, self.settings, cases, self.prepared)
        self.assertNotEqual(after["identity_sha256"], manifest["identity_sha256"])

    def test_unknown_usage_stays_null_and_cannot_be_reported_as_zero_total(self):
        self.execute("--run", "--case", "E01", "--case", "E07")
        summary = self.saved("summary.json")
        unknown = summary["usage"]["resolution_input_tokens"]
        self.assertIsNone(unknown["reported_subtotal"])
        self.assertIsNone(unknown["complete_total"])
        self.assertEqual(unknown["known_cases"], 0)
        self.assertEqual(unknown["unknown_case_ids"], ["E01", "E07"])
        self.assertEqual(summary["usage"]["generation_input_tokens"]["complete_total"], 1000)
        self.assertIsNone(summary["pinecone_charge_usd"])
        self.assertIsNone(summary["local_hardware_cost_usd"])


if __name__ == "__main__":
    unittest.main()
