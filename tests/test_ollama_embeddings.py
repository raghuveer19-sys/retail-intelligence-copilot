"""Simulated local Ollama responses; real-model acceptance is a separate manual run."""

from copy import deepcopy
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from retail_copilot import ollama_embeddings as local, ollama_example
from retail_copilot.chunking import section_chunks
from retail_copilot.documents import PROJECT_ROOT, load_documents, load_settings


class OllamaEmbeddingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = load_settings()
        cls.embedding = cls.settings["embedding"]
        cls.documents = load_documents(PROJECT_ROOT / "data" / "knowledge")
        cls.chunk = next(chunk for doc in cls.documents for chunk in section_chunks(doc)
                         if chunk.id == cls.settings["ollama_example"]["chunk_id"])

    def tags(self):
        return {"models": [{"name": self.embedding["model"], "digest": "fictional-model-digest"}]}

    def response(self):
        return {"model": self.embedding["model"], "embeddings": [[0.1] * self.embedding["dimensions"]],
                "prompt_eval_count": 62, "total_duration": 1_000_000_000}

    def fake_result(self):
        with patch.object(local, "request_local_json", side_effect=[self.tags(), self.response()]):
            return local.embed_local_chunk(self.chunk, self.embedding)

    def test_document_prompt_retains_original_text_and_source(self):
        before = deepcopy(self.chunk)
        with patch.object(local, "request_local_json", side_effect=[self.tags(), self.response()]) as request:
            result = local.embed_local_chunk(self.chunk, self.embedding)
        payload = request.call_args_list[1].args[2]
        self.assertEqual(payload["input"], [f"title: {self.chunk.metadata['document_title']} | text: {self.chunk.page_content}"])
        self.assertFalse(payload["truncate"])
        self.assertEqual(payload["dimensions"], 768)
        self.assertEqual(result["text"], self.chunk.page_content)
        self.assertEqual(result["embedding_input"], payload["input"][0])
        self.assertEqual(result["model_digest"], "fictional-model-digest")
        self.assertEqual(result["usage"]["prompt_tokens"], 62)
        result["metadata"]["section_heading"] = "changed"
        self.assertEqual(self.chunk, before)

    def test_template_must_preserve_passage(self):
        for template in ("title only", "{unknown}: {text}", None):
            with self.subTest(template=template), self.assertRaises(ValueError):
                local.document_input(self.chunk, {**self.embedding, "document_template": template})

    def test_missing_cloud_or_unidentified_models_do_not_embed(self):
        for tags in ({"models": []}, {"models": [{}]}, {"models": None},
                     {"models": [{"name": self.embedding["model"], "digest": ""}]},
                     {"models": [{"name": self.embedding["model"], "digest": "test", "remote_host": "example.invalid"}]}):
            with patch.object(local, "request_local_json", return_value=tags) as request:
                with self.assertRaises(ValueError):
                    local.embed_local_chunk(self.chunk, self.embedding)
                self.assertEqual(request.call_count, 1)
        with patch.object(local, "request_local_json") as request, self.assertRaises(ValueError):
            local.embed_local_chunk(self.chunk, {**self.embedding, "model": "model:cloud"})
        request.assert_not_called()

    def test_bad_vectors_and_usage_are_rejected(self):
        changes = (
            {"model": "different"}, {"embeddings": []}, {"embeddings": [[0.1]]},
            {"embeddings": [[0] * 768]}, {"embeddings": [[float("nan")] * 768]},
            {"prompt_eval_count": True}, {"prompt_eval_count": 2049}, {"total_duration": -1},
        )
        for change in changes:
            with self.subTest(change=list(change)), patch.object(local, "request_local_json", side_effect=[self.tags(), {**self.response(), **change}]):
                with self.assertRaises(ValueError):
                    local.embed_local_chunk(self.chunk, self.embedding)

    def test_remote_or_credentialed_urls_are_rejected_before_contact(self):
        for address in ("https://ollama.com", "http://example.invalid", "http://user:password@localhost:11434",
                        "http://localhost:11434/path", "http://localhost:11434?token=fictional"):
            with self.subTest(address=address), patch.object(local, "build_opener") as opener:
                with self.assertRaises(ValueError):
                    local.request_local_json({**self.embedding, "api_base_url": address}, "/api/tags")
                opener.assert_not_called()

    def test_local_http_payload_and_disabled_proxies_redirects(self):
        opener = Mock()
        opener.open.return_value = io.BytesIO(json.dumps(self.response()).encode("utf-8"))
        with patch.object(local, "build_opener", return_value=opener) as factory:
            local.request_local_json(self.embedding, "/api/embed", {"input": ["fictional policy"]})
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/embed")
        self.assertEqual(json.loads(request.data), {"input": ["fictional policy"]})
        self.assertNotIn("Authorization", request.headers)
        self.assertEqual(factory.call_args.args[0].proxies, {})
        with self.assertRaises(URLError):
            factory.call_args.args[1].redirect_request(None, None, 302, "", {}, "https://example.invalid")

    def test_local_errors_do_not_expose_response_details(self):
        errors = (URLError("fictional-private-detail"), TimeoutError("fictional-private-detail"),
                  HTTPError("local", 400, "fictional-private-detail", {}, None))
        for error in errors:
            opener = Mock()
            opener.open.side_effect = error
            with patch.object(local, "build_opener", return_value=opener), self.assertRaises(ValueError) as caught:
                local.request_local_json(self.embedding, "/api/embed", {})
            self.assertNotIn("fictional-private-detail", str(caught.exception))
        for contents in (b"not-json", b"[]", b'{"error":"fictional-private-detail"}'):
            opener = Mock()
            opener.open.return_value = io.BytesIO(contents)
            with patch.object(local, "build_opener", return_value=opener), self.assertRaises(ValueError):
                local.request_local_json(self.embedding, "/api/tags")

    def test_cli_saves_one_result_and_stops_repeat(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(ollama_example, "PROJECT_ROOT", root), patch.object(ollama_example, "load_settings", return_value=self.settings), patch.object(
                ollama_example, "load_documents", return_value=self.documents,
            ), patch.object(ollama_example, "embed_local_chunk", return_value=self.fake_result()) as embed, redirect_stdout(io.StringIO()):
                self.assertEqual(ollama_example.main(), 0)
                saved = json.loads((root / self.settings["ollama_example"]["output_file"]).read_text(encoding="utf-8"))
                self.assertEqual(saved["text"], self.chunk.page_content)
                self.assertEqual(saved["as_of_date"], self.settings["demo"]["as_of_date"])
                self.assertEqual(len(saved["vector"]), 768)
                self.assertEqual(ollama_example.main(), 1)
                self.assertEqual(embed.call_count, 1)

    def test_cli_rejects_ineligible_source_or_unsafe_output_before_embedding(self):
        for changes in ({"chunk_id": "SIM-1024-v1:checks:section-v1"}, {"output_file": "data/knowledge/source.json"}):
            settings = deepcopy(self.settings)
            settings["ollama_example"].update(changes)
            with patch.object(ollama_example, "load_settings", return_value=settings), patch.object(ollama_example, "embed_local_chunk") as embed, redirect_stdout(io.StringIO()):
                self.assertEqual(ollama_example.main(), 1)
                embed.assert_not_called()


if __name__ == "__main__":
    unittest.main()
