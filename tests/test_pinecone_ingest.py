"""Offline ingestion checks. Dummy vectors never leave these tests."""

from contextlib import redirect_stdout
from copy import deepcopy
from datetime import date
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from pinecone import DenseVectorField, Document, IndexModel, IndexSchema, IndexStatus, ManagedDeployment

from retail_copilot import pinecone_ingest as ingest
from retail_copilot.documents import PROJECT_ROOT, load_documents, load_settings
from retail_copilot.ollama_embeddings import document_input
from retail_copilot.prepare_embeddings import build_embedding_export


class PineconeIngestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = load_settings()
        policies = load_documents(PROJECT_ROOT / "data/knowledge")

        def fake_embed(chunk, embedding, **kwargs):
            return {
                "provider": embedding["provider"], "model": embedding["model"],
                "dimensions": embedding["dimensions"], "model_digest": "a" * 64,
                "chunk_id": chunk.id, "text": chunk.page_content, "metadata": deepcopy(chunk.metadata),
                "embedding_input": document_input(chunk, embedding),
                "document_template": embedding["document_template"],
                "vector": [0.1] * embedding["dimensions"], "usage": {"prompt_tokens": 60},
            }

        with patch("retail_copilot.prepare_embeddings.installed_model_digest", return_value="a" * 64), patch(
            "retail_copilot.prepare_embeddings.embed_local_chunk", side_effect=fake_embed,
        ):
            cls.corpus = build_embedding_export(
                policies, date.fromisoformat(cls.settings["demo"]["as_of_date"]),
                "section-v1", cls.settings["embedding"], {},
            )

    def prepare(self, corpus=None, settings=None):
        # Only intercept the generated JSON read; policies/configuration remain real fixtures.
        actual_read = Path.read_text
        path = PROJECT_ROOT / self.settings["embedding_preparation"]["output_file"]

        def read(file, *args, **kwargs):
            if file == path:
                return json.dumps(self.corpus if corpus is None else corpus)
            return actual_read(file, *args, **kwargs)

        with patch.object(Path, "read_text", read):
            return ingest.prepare_upload(PROJECT_ROOT, self.settings if settings is None else settings)

    def remote(self, prepared, *, exists=False):
        client = MagicMock()
        index = client.index.return_value.__enter__.return_value
        info = IndexModel(
            name=self.settings["retrieval"]["index_name"], host="https://example.svc.pinecone.io",
            schema=IndexSchema(fields={"embedding": DenseVectorField(dimension=768, metric="cosine")}),
            deployment=ManagedDeployment(cloud="aws", region="us-east-1"),
            status=IndexStatus(ready=True, state="Ready"), deletion_protection="disabled",
            tags=ingest.index_tags(prepared),
        )
        client.indexes.exists.return_value = exists
        client.indexes.create.return_value = info
        client.indexes.describe.return_value = info
        fetched = {doc["_id"]: Document(deepcopy(doc)) for doc in prepared["documents"]}
        response = SimpleNamespace(documents=fetched, usage=SimpleNamespace(read_units=4))
        index.documents.fetch.return_value = response
        index.documents.upsert.return_value = SimpleNamespace(upserted_count=33)
        return client, index, info, response

    def test_preparation_preserves_all_sources_and_vectors(self):
        prepared = self.prepare()
        self.assertEqual(prepared["record_count"], 33)
        self.assertEqual(prepared["eligible_documents"], 11)
        self.assertLess(prepared["request_json_bytes"], 1_900_000)
        for doc, record in zip(prepared["documents"], self.corpus["records"]):
            self.assertEqual(doc["_id"], record["chunk_id"])
            self.assertEqual(doc["text"], record["text"])
            self.assertEqual(doc["source_file"], record["metadata"]["source_file"])
            self.assertEqual(doc["embedding"], record["vector"])
        self.assertFalse(any(doc["document_id"] == "SIM-1024-v1" for doc in prepared["documents"]))

    def test_stale_or_malformed_records_rejected_before_network(self):
        changes = [
            lambda c: c.update(as_of_date="2026-10-14"),
            lambda c: c["records"].append(deepcopy(c["records"][0])),
            lambda c: c["records"][0].update(text="Changed policy text"),
            lambda c: c["records"][0]["metadata"].update(version="999"),
            lambda c: c["records"][0].update(model_digest="b" * 64),
            lambda c: c["records"][0].update(vector=[float("nan")] * 768),
            lambda c: c["records"].pop(),
        ]
        for change in changes:
            with self.subTest(change=change):
                corpus = deepcopy(self.corpus)
                change(corpus)
                with self.assertRaises(ingest.IngestionError):
                    self.prepare(corpus)

    def test_wrong_region_and_model_provider_rejected(self):
        for section, key, value in [("retrieval", "region", "us-west-2"), ("embedding", "provider", "openai")]:
            settings = deepcopy(self.settings)
            settings[section][key] = value
            with self.assertRaises(ingest.IngestionError):
                self.prepare(settings=settings)

    def test_create_upload_then_verify_after_count_catches_up(self):
        prepared = self.prepare()
        client, index, _, _ = self.remote(prepared)
        index.describe_namespace.side_effect = [SimpleNamespace(record_count=n) for n in (0, 0, 33)]
        sleep = MagicMock()
        report = ingest.upload_and_verify(client, prepared, self.settings, sleep=sleep)
        self.assertEqual(report["records_written"], 33)
        self.assertEqual(report["records_verified"], 33)
        self.assertEqual(report["reported_fetch_read_units"], [4])
        self.assertFalse(report["retrieval_quality_tested"])
        sleep.assert_called_once_with(2)
        client.indexes.create.assert_called_once()
        index.documents.upsert.assert_called_once()
        self.assertEqual(index.documents.upsert.call_args.kwargs["namespace"], "telecom-demo-v1")
        self.assertEqual(index.documents.upsert.call_args.kwargs["documents"], prepared["documents"])

    def test_identical_repeat_does_not_write(self):
        prepared = self.prepare()
        client, index, _, _ = self.remote(prepared, exists=True)
        index.describe_namespace.return_value = SimpleNamespace(record_count=33)
        report = ingest.upload_and_verify(client, prepared, self.settings)
        self.assertEqual(report["records_written"], 0)
        self.assertFalse(report["index_created"])
        index.documents.upsert.assert_not_called()
        client.indexes.create.assert_not_called()

    def test_different_model_tags_or_dimension_never_overwritten(self):
        prepared = self.prepare()
        for mismatch in ("tags", "dimension"):
            with self.subTest(mismatch=mismatch):
                client, index, info, _ = self.remote(prepared, exists=True)
                if mismatch == "tags":
                    info.tags["model_digest"] = "b" * 64
                else:
                    info.schema.fields["embedding"] = DenseVectorField(dimension=1536, metric="cosine")
                with self.assertRaises(ingest.IngestionError):
                    ingest.upload_and_verify(client, prepared, self.settings)
                index.documents.upsert.assert_not_called()

    def test_different_count_or_content_never_overwritten(self):
        prepared = self.prepare()
        for count in (1, 33):
            client, index, _, response = self.remote(prepared, exists=True)
            index.describe_namespace.return_value = SimpleNamespace(record_count=count)
            response.documents.pop(next(iter(response.documents)))
            with self.assertRaises(ingest.IngestionError):
                ingest.upload_and_verify(client, prepared, self.settings)
            index.documents.upsert.assert_not_called()

    def test_unacknowledged_partial_upload_is_not_retried(self):
        prepared = self.prepare()
        client, index, _, _ = self.remote(prepared)
        index.describe_namespace.return_value = SimpleNamespace(record_count=0)
        index.documents.upsert.return_value = SimpleNamespace(upserted_count=32)
        with self.assertRaisesRegex(ingest.IngestionError, "acknowledge"):
            ingest.upload_and_verify(client, prepared, self.settings)
        index.documents.upsert.assert_called_once()

    def test_wrong_returned_text_or_vector_fails_verification(self):
        prepared = self.prepare()
        for field, value in (("text", "Wrong evidence"), ("embedding", [0.0] * 768)):
            client, index, _, response = self.remote(prepared)
            index.describe_namespace.side_effect = [SimpleNamespace(record_count=0)] + [SimpleNamespace(record_count=33)] * 10
            changed = response.documents[prepared["documents"][0]["_id"]].to_dict()
            changed[field] = value
            response.documents[changed["_id"]] = Document(changed)
            with self.assertRaisesRegex(ingest.IngestionError, "verification"):
                ingest.upload_and_verify(client, prepared, self.settings, sleep=lambda _: None)
            index.documents.upsert.assert_called_once()

    def test_float32_rounding_is_accepted_but_extra_metadata_is_not(self):
        prepared = self.prepare()
        _, _, _, response = self.remote(prepared)
        first = prepared["documents"][0]
        changed = response.documents[first["_id"]].to_dict()
        changed["embedding"] = [0.100000001] * 768
        response.documents[first["_id"]] = Document(changed)
        self.assertTrue(ingest.records_match(response.documents, prepared["documents"], "embedding"))
        changed["unexpected"] = "extra data"
        self.assertFalse(ingest.records_match(response.documents, prepared["documents"], "embedding"))

    def test_default_preview_never_reads_credentials_or_calls_network(self):
        with patch.object(ingest, "prepare_upload", return_value=self.prepare()), patch.object(ingest, "Pinecone") as client, patch.object(
            ingest, "read_credential",
        ) as credential, redirect_stdout(io.StringIO()):
            self.assertEqual(ingest.main([]), 0)
        client.assert_not_called()
        credential.assert_not_called()

    def test_missing_key_and_changed_installed_model_stop_before_pinecone(self):
        for key, digest in (("", "a" * 64), ("test-key", "b" * 64)):
            with patch.object(ingest, "prepare_upload", return_value=self.prepare()), patch.object(ingest, "Pinecone") as client, patch.object(
                ingest, "read_credential", return_value=key,
            ), patch.object(ingest, "installed_model_digest", return_value=digest), redirect_stdout(io.StringIO()):
                self.assertEqual(ingest.main(["--upload"]), 1)
            client.assert_not_called()

    def test_provider_error_body_is_never_printed_or_saved_as_success(self):
        output = io.StringIO()
        with patch.object(ingest, "prepare_upload", return_value=self.prepare()), patch.object(ingest, "Pinecone", side_effect=RuntimeError("secret-provider-body")), patch.object(
            ingest, "read_credential", return_value="test-key",
        ), patch.object(ingest, "installed_model_digest", return_value="a" * 64), patch.object(ingest, "save_chunk_export") as save, redirect_stdout(output):
            self.assertEqual(ingest.main(["--upload"]), 1)
        self.assertNotIn("secret-provider-body", output.getvalue())
        self.assertNotIn("test-key", output.getvalue())
        save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
