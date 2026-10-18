"""Evaluation orchestration tests simulate services; they do not measure model accuracy."""

from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import test_answering as fixtures
from retail_copilot import evaluate
from retail_copilot.answering import build_prompt, render_draft
from retail_copilot.documents import PROJECT_ROOT
from retail_copilot.policy_lookup import plan_lookup


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = fixtures.AnsweringTests
        fixture.setUpClass()
        for name in ("settings", "instructions", "prepared", "result"):
            setattr(cls, name, deepcopy(getattr(fixture, name)))
        cls.cases = evaluate.load_cases(PROJECT_ROOT, cls.settings)
        cls.digest = "d" * 64

    def case(self, identifier="E11"):
        return deepcopy(next(case for case in self.cases if case["test_id"] == identifier))

    def generation(self, pack, instructions, settings, **kwargs):
        preview = build_prompt(pack, instructions, settings)
        draft = {"status": "insufficient_evidence", "claims": [{"text": "The SIM policy requires identity and account-authority checks.",
                                                                  "source_ids": ["S2"]}], "clarifying_question": None}
        return {"artifact_type": "generation_result", "question": pack["question"], "context_text": pack["context_text"],
                **{key: preview[key] for key in ("context_sha256", "instructions_sha256", "messages", "source_registry")},
                "model": settings["generation"]["model"], "model_digest": self.digest, "model_call_made": True,
                "answer_generated": True, "done_reason": "stop",
                "options": {key: settings["generation"][key] for key in ("num_ctx", "num_predict", "temperature")},
                "usage": {"prompt_tokens": 1000, "generated_tokens_including_thinking": 100},
                "draft": draft, "answer": render_draft(json.dumps(draft), pack, settings)}

    def run_case(self, folder, case=None, baselines=None, index=None, instructions=None):
        return evaluate.run_case(case or self.case(), self.prepared, self.settings, instructions or self.instructions,
                                 self.digest, Path(folder), baselines or [], index or Mock(side_effect=AssertionError("No live retrieval allowed")))

    def semantic_result(self, case):
        result = deepcopy(self.result)
        result.update({"question": case["user_question"], "retrieval_mode": "semantic", "top_k": 4, "metric": "cosine",
                       "pinecone_read_units": 1, "query_prompt_tokens": 10, "total_seconds": 0.1})
        for hit in result["matches"]:
            hit["retrieval_method"] = "semantic"
        return result

    def enhanced_result(self, case):
        result = self.semantic_result(case)
        plan = plan_lookup(result, self.prepared, self.settings["policy_lookup"], "embedding")
        records = {record["_id"]: record for record in self.prepared["documents"]}
        for identifier in plan["requested_chunk_ids"]:
            record = records[identifier]
            result["matches"].append({"chunk_id": identifier, "text": record["text"],
                                      "metadata": {key: value for key, value in record.items() if key not in ("_id", "text", "embedding")},
                                      "score": None, "retrieval_method": "policy_lookup"})
        result.update({"retrieval_mode": "semantic_with_policy_lookup", "policy_lookup": plan})
        return result

    def test_controlled_case_has_only_sim_and_no_fabricated_similarity(self):
        result = evaluate.controlled_result(self.case(), self.prepared, self.settings)
        self.assertEqual({hit["metadata"]["document_id"] for hit in result["matches"]}, {"SIM-1024-v2"})
        self.assertEqual(len(result["matches"]), 3)
        self.assertTrue(all(hit["score"] is None and hit["retrieval_method"] == "controlled_context" for hit in result["matches"]))
        pack = evaluate.validate_retrieval(result, self.case(), self.prepared, self.settings)
        self.assertIn("AUTH-1001", pack["references_without_passages"])
        metrics = evaluate.retrieval_metrics(result, self.case())
        self.assertIsNone(metrics["semantic"])
        self.assertIsNone(metrics["with_lookup"])

    def test_controlled_case_rejects_unknown_document_or_missing_section(self):
        case = self.case()
        case["context_document_ids"] = ["SIM-1024-v1"]
        with self.assertRaises(evaluate.EvaluationError):
            evaluate.controlled_result(case, self.prepared, self.settings)
        result = evaluate.controlled_result(self.case(), self.prepared, self.settings)
        result["matches"].pop()
        with self.assertRaises(evaluate.EvaluationError):
            evaluate.validate_retrieval(result, self.case(), self.prepared, self.settings)

    def test_semantic_and_lookup_retrieval_metrics_are_separate(self):
        case = self.case("E05")
        result = self.enhanced_result(case)
        evaluate.validate_retrieval(result, case, self.prepared, self.settings)
        metrics = evaluate.retrieval_metrics(result, case)
        self.assertLess(metrics["semantic"]["matched_count"], metrics["with_lookup"]["matched_count"])
        self.assertIsNotNone(metrics["semantic"]["expected_source_recall_at_k"])
        self.assertIsNone(metrics["with_lookup"]["expected_source_recall_at_k"])

    def test_baseline_evidence_is_reused_and_expected_answers_never_reach_model(self):
        case = self.case("E04")
        case["reference_answer"] = "GOLD_ANSWER_SENTINEL"
        baseline = self.enhanced_result(case)
        with TemporaryDirectory() as folder, patch.object(evaluate, "generate_answer", side_effect=self.generation) as call:
            outcome = self.run_case(folder, case, [baseline])
            self.assertEqual(outcome["result"]["retrieval_source"], "prior_baseline")
            self.assertEqual(outcome["new_pinecone_read_units"], 0)
            self.assertNotIn("GOLD_ANSWER_SENTINEL", json.dumps(call.call_args.args))
            self.assertEqual(call.call_args.kwargs, {"keep_alive_seconds": 300})
            self.assertIsNone(outcome["result"]["answer_metrics"]["claim_support"])

    def test_completed_matching_case_resumes_without_inference(self):
        with TemporaryDirectory() as folder, patch.object(evaluate, "generate_answer", side_effect=self.generation) as call:
            first = self.run_case(folder)
            second = self.run_case(folder)
            self.assertFalse(first["resumed"])
            self.assertTrue(second["resumed"])
            self.assertEqual(second["new_model_calls"], 0)
            self.assertEqual(call.call_count, 1)

    def test_changed_instructions_do_not_reuse_or_overwrite_answer(self):
        with TemporaryDirectory() as folder, patch.object(evaluate, "generate_answer", side_effect=self.generation):
            self.run_case(folder)
            path = Path(folder) / "E11.json"
            before = path.read_bytes()
            with self.assertRaises(evaluate.EvaluationError):
                self.run_case(folder, instructions=self.instructions + "Changed instructions")
            self.assertEqual(path.read_bytes(), before)

    def test_tampered_saved_answer_is_not_resumed(self):
        with TemporaryDirectory() as folder, patch.object(evaluate, "generate_answer", side_effect=self.generation):
            self.run_case(folder)
            path = Path(folder) / "E11.json"
            saved = json.loads(path.read_text(encoding="utf-8"))
            saved["generation"]["draft"]["claims"][0]["text"] = "Tampered claim"
            path.write_text(json.dumps(saved), encoding="utf-8")
            with self.assertRaises(evaluate.EvaluationError):
                self.run_case(folder)

    def test_manifest_prevents_mixing_experiment_settings_after_partial_run(self):
        with TemporaryDirectory() as folder:
            directory = Path(folder)
            first = evaluate.initialise_run(directory, self.cases, self.prepared, self.settings, self.instructions, self.digest)
            self.assertEqual(evaluate.initialise_run(directory, self.cases, self.prepared, self.settings, self.instructions, self.digest), first)
            with self.assertRaises(evaluate.EvaluationError):
                evaluate.initialise_run(directory, self.cases, self.prepared, self.settings, self.instructions + "changed", self.digest)
            self.assertEqual(json.loads((directory / "manifest.json").read_text(encoding="utf-8")), first)

    def test_saved_generation_requires_completed_response_current_options_and_valid_usage(self):
        result = evaluate.controlled_result(self.case(), self.prepared, self.settings)
        pack = evaluate.validate_retrieval(result, self.case(), self.prepared, self.settings)
        for change in ("incomplete", "length", "options", "boolean_tokens", "excess_tokens"):
            generated = self.generation(pack, self.instructions, self.settings)
            if change == "incomplete":
                generated["answer_generated"] = False
            elif change == "length":
                generated["done_reason"] = "length"
            elif change == "options":
                generated["options"]["temperature"] = 0.5
            elif change == "boolean_tokens":
                generated["usage"]["prompt_tokens"] = True
            else:
                generated["usage"]["generated_tokens_including_thinking"] = self.settings["generation"]["num_predict"]
            with self.subTest(change=change), self.assertRaises(evaluate.EvaluationError):
                evaluate.check_generation(generated, pack, self.instructions, self.settings, self.digest)

    def test_failed_generation_leaves_retrieval_ready_for_resume(self):
        with TemporaryDirectory() as folder:
            with patch.object(evaluate, "generate_answer", side_effect=RuntimeError("Private error")):
                with self.assertRaises(RuntimeError):
                    self.run_case(folder)
            self.assertTrue((Path(folder) / "E11-retrieval.json").exists())
            self.assertFalse((Path(folder) / "E11.json").exists())
            with patch.object(evaluate, "generate_answer", side_effect=self.generation):
                outcome = self.run_case(folder)
            self.assertEqual(outcome["result"]["retrieval_source"], "evaluation_cache")

    def test_changed_lookup_settings_reject_saved_baseline(self):
        case = self.case("E04")
        result = self.enhanced_result(case)
        settings = deepcopy(self.settings)
        settings["policy_lookup"]["max_policies"] = 1
        with self.assertRaises(evaluate.EvaluationError):
            evaluate.validate_retrieval(result, case, self.prepared, settings)

    def test_scorecard_does_not_claim_semantic_quality_from_structural_success(self):
        with TemporaryDirectory() as folder, patch.object(evaluate, "generate_answer", side_effect=self.generation):
            outcome = self.run_case(folder)
        summary = evaluate.scorecard([outcome["result"]], [{"test_id": "E01"}], 2)
        self.assertEqual(summary["failed_cases"], 1)
        self.assertEqual(summary["controlled_context_completed"], 1)
        self.assertIsNone(summary["expected_section_recall_with_lookup"])
        self.assertIsNone(summary["answer_quality_pass_rate"])
        self.assertEqual(summary["claim_support_reviewed_cases"], 0)

    def test_preview_does_not_contact_models_credentials_or_services(self):
        output = io.StringIO()
        with patch.object(evaluate, "prepare_upload", return_value=self.prepared), patch.object(evaluate, "inspect_model") as inspect, patch.object(evaluate, "read_credential") as credential, patch.object(evaluate, "Pinecone") as service, redirect_stdout(output):
            self.assertEqual(evaluate.main([]), 0)
        inspect.assert_not_called()
        credential.assert_not_called()
        service.assert_not_called()
        self.assertIn("PREVIEW ONLY", output.getvalue())

    def test_escape_output_directory_rejected_before_services(self):
        with patch.object(evaluate, "inspect_model") as inspect, redirect_stdout(io.StringIO()):
            self.assertEqual(evaluate.main(["--run", "--output-dir", "../elsewhere"]), 1)
        inspect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
