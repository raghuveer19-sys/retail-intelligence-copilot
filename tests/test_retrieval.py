"""Offline query and search checks; synthetic vectors never reach external services."""

from contextlib import redirect_stdout
from copy import deepcopy
from datetime import date
import io
import json
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import httpx
from langchain_core.documents import Document as LangChainDocument
from pinecone import Document, Pinecone, DenseVectorField, IndexModel, IndexSchema, IndexStatus, ManagedDeployment

from retail_copilot import ollama_embeddings as local, retrieve
from retail_copilot.chunking import section_chunks
from retail_copilot.documents import PROJECT_ROOT, approved_documents, load_documents, load_settings
from retail_copilot.pinecone_ingest import index_tags
from retail_copilot.pinecone_records import to_pinecone_record


class QueryEmbeddingTests(unittest.TestCase):
    def setUp(self):
        self.embedding = load_settings()["embedding"]
        self.tags = {"models": [{"name": self.embedding["model"], "digest": "a" * 64}]}
        self.response = {"model": self.embedding["model"], "embeddings": [[0.1] * 768],
                         "prompt_eval_count": 20, "total_duration": 1_000_000_000}

    def test_query_prompt_keeps_question_and_does_not_use_document_prompt(self):
        question = "Do I need an appointment?"
        with patch.object(local, "request_local_json", side_effect=[self.tags, self.response]) as request:
            result = local.embed_local_query(question, self.embedding, "a" * 64)
        payload = request.call_args.args[2]
        self.assertEqual(payload["input"], ["task: search result | query: " + question])
        self.assertFalse(payload["truncate"])
        self.assertEqual(payload["dimensions"], 768)
        self.assertEqual(result["prompt_tokens"], 20)
        self.assertEqual(result["provider_duration_seconds"], 1)

    def test_blank_or_invalid_template_stops_before_model_call(self):
        for question, template in [(" ", "{text}"), (None, "{text}"), ("SIM?", "missing placeholder"), ("SIM?", "{unknown} {text}")]:
            with patch.object(local, "request_local_json") as request, self.assertRaises(ValueError):
                local.embed_local_query(question, {**self.embedding, "query_template": template}, "a" * 64)
            request.assert_not_called()

    def test_changed_model_never_embeds_query(self):
        with patch.object(local, "request_local_json", return_value=self.tags) as request, self.assertRaisesRegex(ValueError, "differs"):
            local.embed_local_query("SIM?", self.embedding, "b" * 64)
        self.assertEqual(request.call_count, 1)

    def test_bad_query_response_is_rejected(self):
        changes = [{"embeddings": [[0.1]]}, {"embeddings": [[0] * 768]},
                   {"embeddings": [[float("nan")] * 768]}, {"embeddings": [[True] * 768]},
                   {"model": "other"}, {"prompt_eval_count": 2049}, {"total_duration": -1}]
        for change in changes:
            with self.subTest(change=list(change)), patch.object(local, "request_local_json", side_effect=[self.tags, {**self.response, **change}]), self.assertRaises(ValueError):
                local.embed_local_query("SIM?", self.embedding, "a" * 64)


class RetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = load_settings()
        cls.as_of = date.fromisoformat(cls.settings["demo"]["as_of_date"])
        policies = approved_documents(load_documents(PROJECT_ROOT / "data/knowledge"), cls.as_of)
        documents = []
        for policy in policies:
            for chunk in section_chunks(policy):
                vector = to_pinecone_record({
                    "provider": "ollama", "model": cls.settings["embedding"]["model"], "dimensions": 768,
                    "chunk_id": chunk.id, "text": chunk.page_content,
                    "metadata": deepcopy(chunk.metadata), "vector": [0.1] * 768,
                }, cls.settings["embedding"])
                documents.append({"_id": vector["id"], "embedding": vector["values"], **vector["metadata"]})
        cls.prepared = {"documents": documents, "model_digest": "a" * 64, "corpus_sha256": "b" * 64,
                        "as_of_date": cls.as_of.isoformat(), "record_count": 33}
        cls.query = {"vector": [0.2] * 768, "embedding_input": "task: search result | query: SIM?", "prompt_tokens": 20}

    def response(self, ids=None):
        selected = self.prepared["documents"][:4] if ids is None else [d for d in self.prepared["documents"] if d["_id"] in ids]
        return SimpleNamespace(namespace="telecom-demo-v1", usage=SimpleNamespace(read_units=1), matches=[
            Document({**{key: deepcopy(value) for key, value in doc.items() if key != "embedding"}, "_score": 0.8 - i / 10})
            for i, doc in enumerate(selected)
        ])

    def test_search_uses_correct_namespace_vector_and_evidence_fields(self):
        index = MagicMock()
        index.documents.search.return_value = self.response()
        with patch.object(retrieve, "embed_local_query", return_value=self.query):
            result = retrieve.retrieve_question(index, "SIM?", self.prepared, self.settings)
        request = index.documents.search.call_args.kwargs
        self.assertEqual(request["namespace"], "telecom-demo-v1")
        self.assertEqual(request["top_k"], 4)
        self.assertEqual(request["score_by"][0].values, self.query["vector"])
        self.assertEqual(request["score_by"][0].field, "embedding")
        self.assertIn("text", request["include_fields"])
        self.assertIn("source_file", request["include_fields"])
        self.assertNotIn("embedding", request["include_fields"])
        self.assertNotIn("filter", request)
        self.assertEqual(result["pinecone_read_units"], 1)
        self.assertEqual(len(result["matches"]), 4)
        self.assertFalse(result["answer_generated"])
        index.documents.upsert.assert_not_called()

    def test_sdk_request_and_response_match_the_real_document_api(self):
        # Exercise the installed SDK serializer/parser while replacing only HTTP.
        client = Pinecone(api_key="offline-test-only")
        response = self.response()
        body = {"namespace": response.namespace, "matches": [hit.to_dict() for hit in response.matches], "usage": {"read_units": 1}}
        with client.index(host="https://offline.svc.pinecone.io") as index, patch.object(
            index._http, "post", return_value=httpx.Response(200, json=body),
        ) as post, patch.object(retrieve, "embed_local_query", return_value=self.query):
            result = retrieve.retrieve_question(index, "SIM?", self.prepared, self.settings)
        client.close()
        self.assertEqual(post.call_args.args[0], "/namespaces/telecom-demo-v1/documents/search")
        self.assertEqual(post.call_args.kwargs["json"]["score_by"][0]["type"], "dense_vector")
        self.assertEqual(result["matches"][0]["chunk_id"], response.matches[0].id)

    def test_results_are_langchain_documents_with_returned_text_and_source(self):
        response = self.response()
        matches = retrieve.validate_matches(response, self.prepared, self.settings)
        self.assertIsInstance(matches[0][0], LangChainDocument)
        self.assertEqual(matches[0][0].page_content, response.matches[0].text)
        self.assertEqual(matches[0][0].metadata["source_file"], response.matches[0].source_file)
        self.assertEqual([score for _, score in matches], [hit.score for hit in response.matches])

    def test_unknown_archived_changed_and_duplicate_evidence_rejected(self):
        for change in ({"_id": "SIM-1024-v1:checks:section-v1"}, {"text": "tampered policy"},
                       {"source_file": "wrong.json"}, {"status": "archived"}, {"_score": float("nan")}):
            response = self.response()
            response.matches[0] = Document({**response.matches[0].to_dict(), **change})
            with self.subTest(change=list(change)), self.assertRaises(retrieve.RetrievalError):
                retrieve.validate_matches(response, self.prepared, self.settings)
        response = self.response()
        response.matches[1] = response.matches[0]
        with self.assertRaises(retrieve.RetrievalError):
            retrieve.validate_matches(response, self.prepared, self.settings)

    def test_missing_metadata_and_wrong_namespace_are_not_silently_filled_in(self):
        response = self.response()
        first = response.matches[0].to_dict()
        first.pop("source_file")
        response.matches[0] = Document(first)
        with self.assertRaises(retrieve.RetrievalError):
            retrieve.validate_matches(response, self.prepared, self.settings)
        response = self.response()
        response.namespace = "another-corpus"
        with self.assertRaises(retrieve.RetrievalError):
            retrieve.validate_matches(response, self.prepared, self.settings)

    def test_empty_matches_remain_empty_and_do_not_invent_an_answer(self):
        index = MagicMock()
        index.documents.search.return_value = self.response(ids=[])
        with patch.object(retrieve, "embed_local_query", return_value=self.query):
            result = retrieve.retrieve_question(index, "SIM?", self.prepared, self.settings)
        self.assertEqual(result["matches"], [])
        self.assertEqual(result["evidence_status"], "no_candidates")
        self.assertFalse(result["answer_generated"])

    def test_top_k_and_timeout_rejected_before_embedding(self):
        for key, value in (("top_k", 0), ("top_k", True), ("top_k", 11), ("request_timeout_seconds", float("nan"))):
            settings = deepcopy(self.settings)
            settings["retrieval"][key] = value
            with patch.object(retrieve, "embed_local_query") as embed, self.assertRaises(retrieve.RetrievalError):
                retrieve.retrieve_question(MagicMock(), "SIM?", self.prepared, settings)
            embed.assert_not_called()

    def test_recall_counts_sections_and_keeps_answer_quality_unmeasured(self):
        case = retrieve.baseline_cases(PROJECT_ROOT, self.settings)[1]  # E04 expects three sections.
        response = self.response(ids=["SIM-1024-v2:checks:section-v1"])
        source = response.matches[0].to_dict()
        result = {"question": case["user_question"], "as_of_date": case["as_of_date"],
                  "matches": [{"metadata": source}]}
        score = retrieve.score_expected_sources(result, case)
        self.assertEqual(score["expected_source_recall_at_k"], 1 / 3)
        self.assertEqual(len(score["missing_sources"]), 2)
        self.assertIsNone(score["answer_groundedness"])
        self.assertIsNone(score["citation_correctness"])

    def test_controlled_context_and_wrong_dates_are_not_normal_retrieval(self):
        case = retrieve.baseline_cases(PROJECT_ROOT, self.settings)[0]
        result = {"question": case["user_question"], "as_of_date": "2026-10-14", "matches": []}
        with self.assertRaises(retrieve.RetrievalError):
            retrieve.score_expected_sources(result, case)
        case["evaluation_mode"] = "controlled_context"
        result["as_of_date"] = case["as_of_date"]
        with self.assertRaises(retrieve.RetrievalError):
            retrieve.score_expected_sources(result, case)

    def test_no_expected_sources_has_undefined_recall(self):
        case = {"test_id": "test", "category": "ambiguous", "user_question": "Which?",
                "as_of_date": "2026-10-15", "evaluation_mode": "end_to_end", "expected_source": []}
        score = retrieve.score_expected_sources({"question": "Which?", "as_of_date": "2026-10-15", "matches": []}, case)
        self.assertIsNone(score["expected_source_recall_at_k"])

    def test_missing_key_prevents_external_search(self):
        with patch.object(retrieve, "prepare_upload", return_value=self.prepared), patch.object(
            retrieve, "read_credential", return_value="",
        ), patch.object(retrieve, "Pinecone") as client, redirect_stdout(io.StringIO()):
            self.assertEqual(retrieve.main([]), 1)
        client.assert_not_called()

    def test_provider_errors_do_not_print_sensitive_body_or_save_success(self):
        output = io.StringIO()
        with patch.object(retrieve, "prepare_upload", return_value=self.prepared), patch.object(retrieve, "read_credential", return_value="offline-test-only"), patch.object(
            retrieve, "Pinecone", side_effect=RuntimeError("sensitive-provider-body"),
        ), patch.object(retrieve, "save_chunk_export") as save, redirect_stdout(output):
            self.assertEqual(retrieve.main([]), 1)
        self.assertNotIn("sensitive-provider-body", output.getvalue())
        self.assertNotIn("offline-test-only", output.getvalue())
        save.assert_not_called()

    def test_cli_validates_index_and_saves_complete_baseline_without_remote_writes(self):
        self.check_cli_baseline(follow_references=False)

    def test_cli_lookup_uses_separate_output_and_keeps_default_search_size(self):
        self.check_cli_baseline(follow_references=True)

    def check_cli_baseline(self, follow_references):
        client = MagicMock()
        active = client.__enter__.return_value
        active.indexes.describe.return_value = IndexModel(
            name=self.settings["retrieval"]["index_name"], host="https://offline.svc.pinecone.io",
            schema=IndexSchema(fields={"embedding": DenseVectorField(dimension=768, metric="cosine")}),
            deployment=ManagedDeployment(cloud="aws", region="us-east-1"),
            status=IndexStatus(ready=True, state="Ready"), deletion_protection="disabled",
            tags=index_tags(self.prepared),
        )
        index = active.index.return_value.__enter__.return_value
        index.documents.search.return_value = self.response()
        records = {doc["_id"]: {key: value for key, value in doc.items() if key != "embedding"}
                   for doc in self.prepared["documents"]}
        index.documents.fetch.side_effect = lambda **request: SimpleNamespace(
            namespace="telecom-demo-v1", usage=SimpleNamespace(read_units=1),
            documents={identifier: Document(deepcopy(records[identifier])) for identifier in request["ids"]},
        )
        with patch.object(retrieve, "Pinecone", return_value=client), patch.object(retrieve, "prepare_upload", return_value=self.prepared), patch.object(
            retrieve, "read_credential", return_value="offline-test-only",
        ), patch.object(retrieve, "embed_local_query", return_value=self.query), patch.object(retrieve, "save_chunk_export") as save, redirect_stdout(io.StringIO()):
            args = ["--baseline", "--follow-references"] if follow_references else ["--baseline"]
            self.assertEqual(retrieve.main(args), 0)
        self.assertEqual(index.documents.search.call_count, 3)
        index.documents.upsert.assert_not_called()
        active.indexes.create.assert_not_called()
        report = save.call_args.args[0]
        self.assertEqual([r["evaluation"]["test_id"] for r in report["results"]], ["E01", "E04", "E06"])
        section = "policy_lookup" if follow_references else "retrieval_example"
        self.assertEqual(save.call_args.args[1], PROJECT_ROOT / self.settings[section]["baseline_output_file"])
        self.assertEqual([call.kwargs["top_k"] for call in index.documents.search.call_args_list], [4, 4, 4])
        if follow_references:
            self.assertTrue(all("policy_lookup" in result for result in report["results"]))
            self.assertGreater(index.documents.fetch.call_count, 0)
        else:
            index.documents.fetch.assert_not_called()

    def test_lookup_output_cannot_replace_original_baseline(self):
        settings = deepcopy(self.settings)
        settings["policy_lookup"]["baseline_output_file"] = settings["retrieval_example"]["baseline_output_file"]
        with patch.object(retrieve, "load_settings", return_value=settings), patch.object(
            retrieve, "prepare_upload", return_value=self.prepared,
        ), patch.object(retrieve, "Pinecone") as client, patch.object(retrieve, "save_chunk_export") as save, redirect_stdout(io.StringIO()):
            self.assertEqual(retrieve.main(["--baseline", "--follow-references"]), 1)
        client.assert_not_called()
        save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
