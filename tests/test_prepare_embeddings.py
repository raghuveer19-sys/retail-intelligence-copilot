"""Corpus preparation with simulated vectors, never model or Pinecone requests."""

from copy import deepcopy
from contextlib import redirect_stdout
from datetime import date
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from retail_copilot import prepare_embeddings as preparation
from retail_copilot.chunking import section_chunks
from retail_copilot.documents import PROJECT_ROOT, load_documents, load_settings
from retail_copilot.ollama_embeddings import document_input


class PrepareEmbeddingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = load_settings()
        cls.embedding = cls.settings["embedding"]
        cls.documents = load_documents(PROJECT_ROOT / "data" / "knowledge")
        cls.as_of = date.fromisoformat(cls.settings["demo"]["as_of_date"])

    def fake_embed(self, chunk, embedding, *, keep_alive="0s"):
        return {
            "provider": embedding["provider"], "model": embedding["model"],
            "dimensions": embedding["dimensions"], "model_digest": "test-digest",
            "chunk_id": chunk.id, "text": chunk.page_content,
            "metadata": deepcopy(chunk.metadata),
            "embedding_input": document_input(chunk, embedding),
            "document_template": embedding["document_template"],
            "vector": [0.1] * embedding["dimensions"],  # Dummy test data only.
            "usage": {"prompt_tokens": 60}, "duration_seconds": 0.1,
        }

    def build(self, cache=None, documents=None):
        return preparation.build_embedding_export(
            self.documents if documents is None else documents, self.as_of, "section-v1",
            self.embedding, {} if cache is None else cache,
        )

    def cached_corpus(self):
        with patch.object(preparation, "installed_model_digest", return_value="test-digest"), patch.object(
            preparation, "embed_local_chunk", side_effect=self.fake_embed,
        ):
            return self.build()

    def test_complete_corpus_has_unique_eligible_ids_and_exact_sources(self):
        with patch.object(preparation, "installed_model_digest", return_value="test-digest"), patch.object(
            preparation, "embed_local_chunk", side_effect=self.fake_embed,
        ) as embed:
            export = self.build()
        self.assertEqual(export["record_count"], 33)
        self.assertEqual(export["eligible_documents"], 11)
        self.assertEqual(export["excluded_document_ids"], ["SIM-1024-v1"])
        self.assertEqual(export["new_input_tokens"], 33 * 60)
        self.assertEqual(embed.call_count, 33)
        self.assertTrue(all(call.kwargs["keep_alive"] == "5m" for call in embed.call_args_list[:-1]))
        self.assertEqual(embed.call_args_list[-1].kwargs["keep_alive"], "0s")
        actual = {c.id: c for d in self.documents for c in section_chunks(d)}
        identifiers = [record["chunk_id"] for record in export["records"]]
        self.assertEqual(identifiers, sorted(set(identifiers)))
        for record in export["records"]:
            self.assertEqual(record["text"], actual[record["chunk_id"]].page_content)
            self.assertEqual(record["metadata"], actual[record["chunk_id"]].metadata)

    def test_unchanged_rerun_reuses_all_without_embedding(self):
        first = self.cached_corpus()
        cache = {record["chunk_id"]: record for record in first["records"]}
        before = deepcopy(cache)
        with patch.object(preparation, "installed_model_digest", return_value="test-digest"), patch.object(preparation, "embed_local_chunk") as embed:
            result = self.build(cache)
        embed.assert_not_called()
        self.assertEqual(result["reused_records"], 33)
        self.assertEqual(result["new_records"], 0)
        self.assertEqual(result["new_input_tokens"], 0)
        self.assertEqual(result["records"], first["records"])
        self.assertEqual(cache, before)

    def test_old_model_input_usage_or_invalid_vector_cannot_be_reused(self):
        chunk = section_chunks(self.documents[0])[0]
        initial = self.fake_embed(chunk, self.embedding)
        changes = {
            "model": "different", "model_digest": "old", "provider": "different",
            "dimensions": 4, "text": "changed", "embedding_input": "changed",
            "document_template": "changed", "vector": [0.1],
            "usage": {"prompt_tokens": True},
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                self.assertIsNone(preparation.reusable_result({**initial, field: value}, chunk, self.embedding, "test-digest"))

    def test_changed_passage_reembeds_only_that_passage(self):
        prior = self.cached_corpus()
        cache = {record["chunk_id"]: record for record in prior["records"]}
        documents = deepcopy(self.documents)
        authority = next(doc for doc in documents if doc.id == "AUTH-1001-v1")
        authority.metadata["sections"][0]["text"] += " Fictional clarification."
        with patch.object(preparation, "installed_model_digest", return_value="test-digest"), patch.object(
            preparation, "embed_local_chunk", side_effect=self.fake_embed,
        ) as embed:
            export = self.build(cache, documents)
        self.assertEqual(embed.call_count, 1)
        self.assertEqual(export["reused_records"], 32)
        self.assertIn("Fictional clarification.", embed.call_args.args[0].page_content)

    def test_metadata_only_change_refreshes_source_without_reembedding(self):
        chunk = section_chunks(self.documents[0])[0]
        saved = self.fake_embed(chunk, self.embedding)
        chunk.metadata["owner"] = "Updated Fictional Knowledge Team"
        result = preparation.reusable_result(saved, chunk, self.embedding, "test-digest")
        self.assertEqual(result["metadata"]["owner"], chunk.metadata["owner"])
        self.assertNotEqual(result["metadata"]["owner"], saved["metadata"]["owner"])

    def test_removed_source_is_not_kept_from_cache(self):
        prior = self.cached_corpus()
        cache = {record["chunk_id"]: record for record in prior["records"]}
        documents = [doc for doc in self.documents if doc.id != "AUTH-1001-v1"]
        with patch.object(preparation, "installed_model_digest", return_value="test-digest"), patch.object(preparation, "embed_local_chunk") as embed:
            export = self.build(cache, documents)
        embed.assert_not_called()
        self.assertEqual(export["record_count"], 30)
        self.assertFalse(any(record["metadata"]["document_id"] == "AUTH-1001-v1" for record in export["records"]))

    def test_model_change_during_run_is_rejected(self):
        with patch.object(preparation, "installed_model_digest", return_value="different-digest"), patch.object(
            preparation, "embed_local_chunk", side_effect=self.fake_embed,
        ), self.assertRaisesRegex(ValueError, "model changed"):
            self.build()

    def test_no_eligible_evidence_or_unsupported_strategy_never_calls_model(self):
        with patch.object(preparation, "installed_model_digest") as model:
            for as_of, strategy in ((date(2026, 9, 1), "section-v1"), (self.as_of, "unknown")):
                with self.subTest(strategy=strategy), self.assertRaises(ValueError):
                    preparation.build_embedding_export(self.documents, as_of, strategy, self.embedding, {})
            model.assert_not_called()

    def test_cache_file_priority_and_malformed_files(self):
        with tempfile.TemporaryDirectory() as folder:
            first, second = Path(folder) / "first.json", Path(folder) / "second.json"
            first.write_text(json.dumps({"records": [{"chunk_id": "one", "model": "first"}]}), encoding="utf-8")
            second.write_text(json.dumps({"chunk_id": "one", "model": "fallback"}), encoding="utf-8")
            self.assertEqual(preparation.load_cached_results([first, second])["one"]["model"], "first")
            for contents in ("not-json", "[]", '{"records":{}}', '{"records":[{"chunk_id":"one"},{"chunk_id":"one"}]}'):
                first.write_text(contents, encoding="utf-8")
                with self.assertRaises(ValueError):
                    preparation.load_cached_results([first])

    def test_failed_model_request_preserves_previous_complete_file(self):
        previous = self.cached_corpus()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = root / self.settings["embedding_preparation"]["output_file"]
            output.parent.mkdir(parents=True)
            original = json.dumps(previous)
            output.write_text(original, encoding="utf-8")
            with patch.object(preparation, "PROJECT_ROOT", root), patch.object(preparation, "load_settings", return_value=self.settings), patch.object(
                preparation, "load_documents", return_value=self.documents,
            ), patch.object(preparation, "installed_model_digest", return_value="new-digest"), patch.object(
                preparation, "embed_local_chunk", side_effect=ValueError("Local model unavailable"),
            ), redirect_stdout(io.StringIO()) as printed:
                self.assertEqual(preparation.main(), 1)
            self.assertEqual(output.read_text(encoding="utf-8"), original)
            self.assertIn("No complete replacement", printed.getvalue())

    def test_generated_paths_cannot_point_at_source_files(self):
        for name in ("data/knowledge/source.json", "../outside.json", "data/processed/output.txt"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                preparation.generated_json_path(PROJECT_ROOT, name)


if __name__ == "__main__":
    unittest.main()
