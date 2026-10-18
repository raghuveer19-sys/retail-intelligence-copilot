"""Evidence-pack tests use fictional local sources and simulate no model answers."""

from contextlib import redirect_stdout
from copy import deepcopy
from datetime import date
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from retail_copilot import context
from retail_copilot.chunking import section_chunks
from retail_copilot.documents import PROJECT_ROOT, approved_documents, load_documents, load_settings
from retail_copilot.pinecone_records import to_pinecone_record


SIM = "SIM-1024-v2:checks:section-v1"
AUTH = "AUTH-1001-v1:roles:section-v1"
IDV = "IDV-1001-v1:training_id:section-v1"


class ContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = load_settings()
        policies = approved_documents(load_documents(PROJECT_ROOT / "data/knowledge"), date(2026, 10, 15))
        cls.records = {}
        for policy in policies:
            for chunk in section_chunks(policy):
                mapped = to_pinecone_record({
                    "provider": "ollama", "model": cls.settings["embedding"]["model"], "dimensions": 768,
                    "chunk_id": chunk.id, "text": chunk.page_content,
                    "metadata": deepcopy(chunk.metadata), "vector": [0.1] * 768,
                }, cls.settings["embedding"])
                cls.records[chunk.id] = {"_id": chunk.id, "embedding": mapped["values"], **mapped["metadata"]}
        cls.prepared = {"documents": list(cls.records.values()), "as_of_date": "2026-10-15",
                        "model_digest": "a" * 64, "corpus_sha256": "b" * 64}

    def result(self, ids=(SIM, AUTH, IDV)):
        hits = []
        for identifier in ids:
            fields = deepcopy(self.records[identifier])
            fields.pop("_id")
            fields.pop("embedding")
            text = fields.pop("text")
            fetched = identifier == IDV
            hits.append({"chunk_id": identifier, "text": text, "metadata": fields,
                         "score": None if fetched else 0.5,
                         "retrieval_method": "policy_lookup" if fetched else "semantic"})
        return {"schema_version": 1, "question": "What checks apply to a fictional SIM replacement?",
                "as_of_date": "2026-10-15", "model": self.settings["embedding"]["model"], "dimensions": 768,
                "model_digest": "a" * 64, "corpus_sha256": "b" * 64,
                "index_name": self.settings["retrieval"]["index_name"], "namespace": self.settings["retrieval"]["namespace"],
                "matches": hits, "evaluation": {"test_id": "E04"}}

    def build(self, result=None, **limits):
        settings = deepcopy(self.settings)
        settings["context"].update(limits)
        return context.build_context(self.result() if result is None else result, self.prepared, settings)

    def test_whole_passages_and_source_labels_map_to_actual_metadata(self):
        result = self.result()
        before = deepcopy(result)
        pack = self.build(result)
        evidence = json.loads(pack["context_text"])
        self.assertEqual(result, before)
        self.assertEqual(evidence["question"], result["question"])
        self.assertEqual(len(evidence["sources"]), 3)
        for label, hit, source in zip(("S1", "S2", "S3"), result["matches"], evidence["sources"], strict=True):
            self.assertEqual(source["source_id"], label)
            self.assertEqual(source["text"], hit["text"])
            self.assertEqual(source["source_file"], hit["metadata"]["source_file"])
            self.assertEqual(pack["source_registry"][label]["chunk_id"], hit["chunk_id"])
            self.assertEqual(pack["source_registry"][label]["metadata"], hit["metadata"])
        self.assertIsNone(pack["source_registry"]["S3"]["similarity_score"])
        self.assertNotIn("score", pack["context_text"])
        self.assertNotIn("embedding", pack["context_text"])
        self.assertIsNone(pack["model_input_tokens"])
        self.assertFalse(pack["generation_attempted"])

    def test_same_input_keeps_labels_order_and_text_deterministic(self):
        self.assertEqual(self.build(), self.build())

    def test_controlled_context_is_labelled_and_has_no_search_scores(self):
        result = self.result(ids=(SIM,))
        result["retrieval_mode"] = "controlled_context"
        result["matches"][0].update({"retrieval_method": "controlled_context", "score": None})
        pack = self.build(result)
        self.assertEqual(pack["retrieval_mode"], "controlled_context")
        self.assertEqual(pack["source_registry"]["S1"]["retrieval_method"], "controlled_context")
        self.assertIsNone(pack["source_registry"]["S1"]["similarity_score"])

    def test_controlled_context_rejects_mixed_methods_or_invented_scores(self):
        for mode, method, score in (("controlled_context", "semantic", 0.5),
                                    ("controlled_context", "policy_lookup", None),
                                    ("semantic", "controlled_context", None),
                                    ("controlled_context", "controlled_context", 0.5)):
            result = self.result(ids=(SIM,))
            result["retrieval_mode"] = mode
            result["matches"][0].update({"retrieval_method": method, "score": score})
            with self.subTest(mode=mode, method=method, score=score), self.assertRaises(context.ContextError):
                self.build(result)

    def test_exact_duplicate_ids_removed_without_merging_different_sources(self):
        result = self.result()
        result["matches"].insert(1, deepcopy(result["matches"][0]))
        pack = self.build(result)
        self.assertEqual(pack["input_passage_count"], 4)
        self.assertEqual(pack["selected_source_count"], 3)
        self.assertEqual(pack["duplicate_chunk_ids_removed"], [SIM])
        self.assertEqual([entry["chunk_id"] for entry in pack["source_registry"].values()], [SIM, AUTH, IDV])

    def test_conflicting_duplicate_stops(self):
        result = self.result()
        repeated = deepcopy(result["matches"][0])
        repeated["score"] = 0.6
        result["matches"].append(repeated)
        with self.assertRaisesRegex(context.ContextError, "copies"):
            self.build(result)

    def test_same_text_with_different_source_ids_is_not_collapsed(self):
        result = self.result(ids=(SIM, AUTH))
        prepared = deepcopy(self.prepared)
        text = result["matches"][0]["text"]
        result["matches"][1]["text"] = text
        next(doc for doc in prepared["documents"] if doc["_id"] == AUTH)["text"] = text
        pack = context.build_context(result, prepared, self.settings)
        self.assertEqual(pack["selected_source_count"], 2)

    def test_unknown_archived_changed_or_incomplete_sources_rejected(self):
        for change in ("unknown", "archive", "text", "source_file", "missing", "reserved"):
            result = self.result()
            hit = result["matches"][0]
            if change in ("unknown", "archive"):
                hit["chunk_id"] = "UNKNOWN" if change == "unknown" else "SIM-1024-v1:checks:section-v1"
            elif change == "text":
                hit["text"] = "Changed requirement"
            elif change == "missing":
                hit["metadata"].pop("source_file")
            else:
                hit["metadata"]["source_file" if change == "source_file" else "text"] = "Wrong metadata"
            with self.subTest(change=change), self.assertRaises(context.ContextError):
                self.build(result)

    def test_stale_corpus_model_date_or_destination_stops(self):
        for key in ("model", "model_digest", "corpus_sha256", "as_of_date", "index_name", "namespace", "dimensions"):
            result = self.result()
            result[key] = "changed"
            with self.subTest(key=key), self.assertRaises(context.ContextError):
                self.build(result)

    def test_invalid_question_or_matches_stops(self):
        for key, value in (("question", " "), ("question", None), ("matches", {}), ("matches", [None])):
            result = self.result()
            result[key] = value
            with self.assertRaises(context.ContextError):
                self.build(result)

    def test_missing_policy_reference_notice_is_not_a_sufficiency_judgement(self):
        pack = self.build(self.result(ids=(SIM, AUTH)))
        self.assertEqual(pack["references_without_passages"], ["IDV-1001"])
        self.assertEqual(pack["evidence_sufficiency"], "not_assessed")
        complete = self.build()
        self.assertEqual(complete["references_without_passages"], [])
        self.assertEqual(complete["evidence_sufficiency"], "not_assessed")

    def test_empty_retrieval_has_no_invented_source_or_answer(self):
        pack = self.build(self.result(ids=()))
        self.assertEqual(pack["source_registry"], {})
        self.assertEqual(json.loads(pack["context_text"])["sources"], [])
        self.assertEqual(pack["evidence_sufficiency"], "no_retrieved_evidence")
        self.assertFalse(pack["answer_generated"])

    def test_budgets_include_question_headers_and_complete_sections(self):
        pack = self.build()
        size = len(pack["context_text"])
        exact = self.build(max_sources=3, max_characters=size)
        self.assertEqual(exact["context_text"], pack["context_text"])
        for limits in ({"max_sources": 2}, {"max_characters": size - 1}):
            with self.assertRaisesRegex(context.ContextError, "no .* cut"):
                self.build(**limits)
        result = self.result()
        result["question"] += " more question text" * 100
        with self.assertRaises(context.ContextError):
            self.build(result, max_characters=size)

    def test_invalid_limits_rejected(self):
        for limits in ({"max_sources": True}, {"max_sources": 0}, {"max_sources": 21},
                       {"max_characters": -1}, {"max_characters": 100001}, {"max_characters": 1.5}):
            with self.assertRaises(context.ContextError):
                self.build(**limits)

    def test_search_scores_and_fetch_no_score_are_preserved(self):
        for position, change in ((0, {"score": None}), (0, {"score": float("nan")}),
                                 (0, {"score": True}), (0, {"retrieval_method": "invented"}), (2, {"score": 0.5})):
            result = self.result()
            result["matches"][position].update(change)
            with self.assertRaises(context.ContextError):
                self.build(result)

    def test_quoted_instruction_like_text_remains_source_data(self):
        result = self.result(ids=(SIM,))
        prepared = deepcopy(self.prepared)
        text = 'Fictional example: "ignore instructions" is quoted data. Café costs £0.\nKeep the condition.'
        result["matches"][0]["text"] = text
        next(doc for doc in prepared["documents"] if doc["_id"] == SIM)["text"] = text
        pack = context.build_context(result, prepared, self.settings)
        self.assertEqual(json.loads(pack["context_text"])["sources"][0]["text"], text)
        self.assertGreater(pack["context_utf8_bytes"], pack["context_characters"])

    def test_evaluation_answers_and_expected_sources_cannot_change_pack(self):
        result = self.result()
        expected = self.build(result)
        result["evaluation"].update({"expected_source": [{"document_id": "FAKE"}], "reference_answer": "Do not copy this answer."})
        result["answer"] = "An invented answer"
        saved = {"schema_version": 1, "results": [result]}
        self.assertEqual(self.build(context.select_result(saved, "E04")), expected)

    def test_case_selection_rejects_missing_duplicate_and_malformed_cases(self):
        for saved in ({}, {"schema_version": 1, "results": []},
                      {"schema_version": 1, "results": [self.result(), self.result()]},
                      {"schema_version": 1, "results": [None]}):
            with self.assertRaises(context.ContextError):
                context.select_result(saved, "E04")

    def run_cli(self, root, settings, output):
        with patch.object(context, "PROJECT_ROOT", root), patch.object(context, "load_settings", return_value=settings), patch.object(
            context, "prepare_upload", return_value=self.prepared,
        ), patch("socket.socket.connect", side_effect=AssertionError("No network permitted")), patch(
            "retail_copilot.readiness.read_credential", side_effect=AssertionError("No credentials needed"),
        ), redirect_stdout(output):
            return context.main([])

    def write_input(self, root, settings):
        path = root / settings["context"]["input_file"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"schema_version": 1, "results": [self.result()]}), encoding="utf-8")
        return path

    def test_cli_writes_preview_without_network_and_preserves_saved_retrieval(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            input_path = self.write_input(root, self.settings)
            before = input_path.read_bytes()
            output = io.StringIO()
            self.assertEqual(self.run_cli(root, self.settings, output), 0)
            pack = json.loads((root / self.settings["context"]["output_file"]).read_text(encoding="utf-8"))
            self.assertEqual(pack["service_calls_made"], 0)
            self.assertEqual(pack["case_id"], "E04")
            self.assertEqual(input_path.read_bytes(), before)
            self.assertIn("[S3]", output.getvalue())
            self.assertEqual(self.run_cli(root, self.settings, io.StringIO()), 0)

    def test_cli_refuses_to_replace_inputs_other_artifacts_or_source_files(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            input_path = self.write_input(root, self.settings)
            for name in (self.settings["context"]["input_file"], "README.md", "data/processed/other-report.json"):
                settings = deepcopy(self.settings)
                settings["context"]["output_file"] = name
                path = root / name
                if path != input_path:
                    path.write_text('{"artifact_type": "other"}', encoding="utf-8")
                before = path.read_bytes()
                self.assertEqual(self.run_cli(root, settings, io.StringIO()), 1)
                self.assertEqual(path.read_bytes(), before)

    def test_failed_build_keeps_previous_preview_and_sanitizes_parse_errors(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            input_path = self.write_input(root, self.settings)
            self.assertEqual(self.run_cli(root, self.settings, io.StringIO()), 0)
            path = root / self.settings["context"]["output_file"]
            before = path.read_bytes()
            settings = deepcopy(self.settings)
            settings["context"]["max_characters"] = 1
            self.assertEqual(self.run_cli(root, settings, io.StringIO()), 1)
            self.assertEqual(path.read_bytes(), before)
            input_path.write_text("sensitive invalid input", encoding="utf-8")
            output = io.StringIO()
            self.assertEqual(self.run_cli(root, self.settings, output), 1)
            self.assertNotIn("sensitive invalid input", output.getvalue())
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
