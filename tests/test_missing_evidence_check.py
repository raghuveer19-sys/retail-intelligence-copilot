"""Offline checks for the controlled runner; no real model or Pinecone calls."""

from contextlib import redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import test_answering as fixtures
from retail_copilot.answering import render_draft, revalidate_pack
from retail_copilot.context import build_context
from retail_copilot.documents import PROJECT_ROOT
from retail_copilot.evaluate import controlled_result, load_cases


spec = importlib.util.spec_from_file_location("missing_evidence_check", PROJECT_ROOT / "scripts/check_missing_evidence.py")
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


class MissingEvidenceCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = fixtures.AnsweringTests
        fixture.setUpClass()
        cls.settings = deepcopy(fixture.settings)
        cls.settings["answering"]["presentation"] = "source_passages"
        case = next(case for case in load_cases(PROJECT_ROOT, cls.settings) if case["test_id"] == "E11")
        retrieval = controlled_result(case, fixture.prepared, cls.settings)
        pack = revalidate_pack(build_context(retrieval, fixture.prepared, cls.settings), fixture.prepared, cls.settings)
        cls.inputs = {"case": case, "controlled_retrieval": retrieval, "context": pack,
                      "instructions": fixture.instructions, "input_file_sha256": {"fixture": "a" * 64}}

    def generation(self):
        pack = self.inputs["context"]
        source = next(source for source in json.loads(pack["context_text"])["sources"] if source["section_id"] == "checks")
        draft = {"status": "insufficient_evidence", "clarifying_question": None,
                 "claims": [{"text": source["text"], "source_ids": [source["source_id"]]}]}
        return {"draft": draft, "answer": render_draft(json.dumps(draft), pack, self.settings),
                "usage": {"prompt_tokens": 1000, "generated_tokens_including_thinking": 120},
                "model_call_made": True, "generation_seconds": 1.0,
                "external_request_charge_usd": "0", "local_hardware_cost_usd": None}

    def test_preview_has_no_generation_or_output(self):
        with TemporaryDirectory() as directory, patch.object(check, "PROJECT_ROOT", Path(directory)), patch.object(
            check, "load_settings", return_value=self.settings,
        ), patch.object(check, "prepare_check", return_value=self.inputs), patch.object(check, "generate_answer") as generate:
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(check.main([]), 0)
            generate.assert_not_called()
            self.assertFalse((Path(directory) / "data").exists())
            self.assertIn("PREVIEW ONLY", output.getvalue())

    def test_run_retains_raw_and_final_evidence_without_adding_missing_policies(self):
        generation = self.generation()
        before = deepcopy(generation)
        with patch.object(check, "generate_answer", return_value=generation) as generate:
            artifact = check.run_check(self.inputs, self.settings)
        generate.assert_called_once_with(self.inputs["context"], self.inputs["instructions"], self.settings)
        self.assertEqual(generation, before)
        self.assertEqual(artifact["generation_result"], before)
        diagnostics = artifact["result"]["diagnostics"]
        self.assertEqual(diagnostics["generation"]["model_draft"], before["draft"])
        self.assertEqual({entry["metadata"]["document_id"] for entry in diagnostics["context"]["source_registry"].values()}, {"SIM-1024-v2"})
        self.assertTrue(all(hit["score"] is None for hit in diagnostics["controlled_retrieval"]["matches"]))
        self.assertEqual(set(diagnostics["generation"]["source_assembly"]["referenced_policy_ids_without_passages"]), {"IDV-1001", "AUTH-1001"})
        self.assertEqual(artifact["result"]["status"], "insufficient_evidence")
        self.assertIn("Here is the available policy guidance", artifact["result"]["text"])
        self.assertIn("AUTH-1001, IDV-1001", artifact["result"]["text"])
        self.assertIn("can't confirm those requirements", artifact["result"]["text"])
        self.assertEqual(artifact["usage"]["pinecone_read_units"], 0)
        self.assertIsNone(artifact["retrieval_review"]["expected_section_recall"])
        self.assertIn("not chat end-to-end", artifact["scope"])
        self.assertIn("pending", artifact["semantic_review"])
        self.assertNotIn("reference_answer", json.dumps(self.inputs["context"]))

    def test_existing_output_stops_before_any_preparation_or_generation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / check.DEFAULT_OUTPUT
            target.parent.mkdir(parents=True)
            target.write_text("previous evidence", encoding="utf-8")
            with patch.object(check, "PROJECT_ROOT", root), patch.object(check, "prepare_check") as prepare, patch.object(check, "generate_answer") as generate, redirect_stdout(io.StringIO()):
                self.assertEqual(check.main(["--run"]), 1)
            prepare.assert_not_called()
            generate.assert_not_called()
            self.assertEqual(target.read_text(encoding="utf-8"), "previous evidence")

    def test_model_failure_has_no_result_file_or_provider_detail(self):
        with TemporaryDirectory() as directory, patch.object(check, "PROJECT_ROOT", Path(directory)), patch.object(
            check, "load_settings", return_value=self.settings,
        ), patch.object(check, "prepare_check", return_value=self.inputs), patch.object(
            check, "generate_answer", side_effect=ValueError("PRIVATE_PROVIDER_DETAIL"),
        ):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(check.main(["--run"]), 1)
            self.assertNotIn("PRIVATE_PROVIDER_DETAIL", output.getvalue())
            self.assertFalse((Path(directory) / check.DEFAULT_OUTPUT).exists())


if __name__ == "__main__":
    unittest.main()
