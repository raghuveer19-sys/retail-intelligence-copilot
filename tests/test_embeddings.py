"""Fictional API responses only: no test contacts OpenAI or creates production vectors."""

import copy
import io
import json
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx2
from langchain_core.documents import Document
from openai import OpenAI

from retail_copilot import embed_example, embeddings
from retail_copilot.chunking import section_chunks
from retail_copilot.documents import PROJECT_ROOT, load_documents, load_settings
from retail_copilot.token_report import load_pricing


class EmbeddingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = load_settings()
        cls.library = load_documents(PROJECT_ROOT / "data" / "knowledge")
        authority = next(doc for doc in cls.library if doc.id == "AUTH-1001-v1")
        cls.chunk = next(chunk for chunk in section_chunks(authority) if chunk.metadata["section_id"] == "delegation")
        cls.price = load_pricing(PROJECT_ROOT / "config" / "pricing.yaml")
        cls.price = {**cls.price, "paid_service_use_enabled": True}  # Test fixture only.
        cls.embedding = cls.settings["openai_embedding"]
        cls.preview = embeddings.preview_embedding(cls.chunk, cls.embedding, cls.price)

    def fake_response(self):
        return {
            "object": "list", "model": self.embedding["model"],
            "data": [{"object": "embedding", "index": 0, "embedding": [0.1] * 1536}],
            "usage": {"prompt_tokens": 50, "total_tokens": 50},
        }

    @contextmanager
    def mock_api(self, payload=None, status=200, timeout=False):
        calls = []
        def handler(request):
            calls.append(request)
            if timeout:
                raise httpx2.ReadTimeout("fictional-private-detail", request=request)
            return httpx2.Response(status, json=self.fake_response() if payload is None else payload)
        transport = httpx2.MockTransport(handler)
        with OpenAI(
            api_key="fictional-test-key", base_url="https://example.invalid/v1",
            http_client=httpx2.Client(transport=transport), max_retries=0,
        ) as client, patch("socket.socket.connect", side_effect=AssertionError("Unexpected network attempt")):
            yield client, calls

    def embed(self, client, chunk=None, price=None, allowance=Decimal("0.001"), embedding=None):
        return embeddings.embed_one_chunk(
            self.chunk if chunk is None else chunk,
            self.embedding if embedding is None else embedding,
            self.price if price is None else price, client, allowance,
        )

    @contextmanager
    def command_context(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            settings = copy.deepcopy(self.settings)
            pricing = copy.deepcopy(self.price)
            with patch.object(embed_example, "PROJECT_ROOT", root), patch.object(
                embed_example, "load_settings", return_value=settings,
            ), patch.object(embed_example, "load_documents", return_value=self.library), patch.object(
                embed_example, "load_pricing", return_value=pricing,
            ), patch.object(embed_example, "read_credential", return_value="fictional-private-key") as key:
                yield root, settings, pricing, key

    def run_cli(self, args):
        with redirect_stdout(io.StringIO()) as messages:
            status = embed_example.main(args)
        return status, messages.getvalue()

    def test_preview_measures_known_example_without_credential_or_client_access(self):
        self.assertEqual(self.preview["total_tokens"], 50)
        self.assertEqual(self.preview["estimated_usd"], Decimal("0.000001"))
        with self.command_context() as (_, _, _, key), patch.object(embed_example, "OpenAI") as client, patch.object(
            embed_example, "save_chunk_export",
        ) as save:
            status, messages = self.run_cli([])
            self.assertEqual(status, 0)
            self.assertIn("PREVIEW ONLY", messages)
            self.assertIn("no vector and no result file", messages)
            key.assert_not_called()
            client.assert_not_called()
            save.assert_not_called()

    def test_installed_sdk_sends_exact_text_and_keeps_metadata_local(self):
        before = copy.deepcopy(self.chunk.model_dump())
        with self.mock_api() as (client, calls):
            result = self.embed(client)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].url.path, "/v1/embeddings")
        self.assertEqual(json.loads(calls[0].content), {
            "model": self.embedding["model"], "input": [self.chunk.page_content],
            "dimensions": 1536, "encoding_format": "float",
        })
        self.assertEqual(result["chunk_id"], self.chunk.id)
        self.assertEqual(result["text"], self.chunk.page_content)
        self.assertEqual(result["metadata"], self.chunk.metadata)
        self.assertEqual(len(result["vector"]), 1536)
        result["metadata"]["source_file"] = "changed-only-in-result.json"
        self.assertEqual(self.chunk.model_dump(), before)

    def test_cost_uses_returned_usage_and_preserves_local_estimate(self):
        response = self.fake_response()
        response["usage"] = {"prompt_tokens": 51, "total_tokens": 51}
        with self.mock_api(payload=response) as (client, _):
            result = self.embed(client)
        self.assertEqual(result["local_input_tokens"], 50)
        self.assertEqual(result["usage"]["prompt_tokens"], 51)
        self.assertEqual(Decimal(result["pre_request_estimate_usd"]), Decimal("0.000001"))
        self.assertEqual(Decimal(result["usage_based_cost_usd"]), Decimal("0.00000102"))

    def test_disabled_service_use_and_bad_allowances_never_send(self):
        client = Mock()
        for allowance in (None, Decimal("0"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity"), Decimal("0.0000001")):
            with self.subTest(allowance=allowance), self.assertRaises(ValueError):
                self.embed(client, allowance=allowance)
        for enabled in (False, "true", 1):
            with self.subTest(enabled=enabled), self.assertRaisesRegex(ValueError, "disabled"):
                self.embed(client, price={**self.price, "paid_service_use_enabled": enabled})
        client.embeddings.create.assert_not_called()

    def test_exact_estimated_allowance_is_accepted(self):
        with self.mock_api() as (client, calls):
            self.embed(client, allowance=Decimal("0.000001"))
        self.assertEqual(len(calls), 1)

    def test_invalid_inputs_are_rejected_before_any_request(self):
        client = Mock()
        for text in ("", " \n", "hello" + " hello" * 8192):
            with self.subTest(text_length=len(text)), self.assertRaises(ValueError):
                self.embed(client, chunk=Document(id="fictional", page_content=text))
        for dimensions in (0, -1, True, 1.5):
            with self.subTest(dimensions=dimensions), self.assertRaises(ValueError):
                self.embed(client, embedding={**self.embedding, "dimensions": dimensions})
        client.embeddings.create.assert_not_called()

    def test_wrong_model_count_and_index_are_rejected(self):
        for change in ("model", "empty", "multiple", "index"):
            response = self.fake_response()
            if change == "model":
                response["model"] = "different-model"
            elif change == "empty":
                response["data"] = []
            elif change == "multiple":
                response["data"] *= 2
            else:
                response["data"][0]["index"] = 1
            with self.subTest(change=change), self.mock_api(payload=response) as (client, _):
                with self.assertRaisesRegex(ValueError, "response failed validation"):
                    self.embed(client)

    def test_wrong_length_nonfinite_nonnumeric_and_zero_vectors_are_rejected(self):
        for vector in ([0.1], [0.0] * 1536, [float("nan")] * 1536, [float("inf")] * 1536, [True] * 1536, ["0.1"] * 1536):
            response = SimpleNamespace(
                model=self.embedding["model"], data=[SimpleNamespace(index=0, embedding=vector)],
                usage=SimpleNamespace(prompt_tokens=50, total_tokens=50),
            )
            with self.subTest(first_value=vector[0]), self.assertRaisesRegex(ValueError, "response failed validation"):
                embeddings.validate_response(response, self.embedding["model"], 1536)

    def test_missing_or_invalid_usage_is_rejected(self):
        for usage in (None, {}, {"prompt_tokens": -1, "total_tokens": -1}, {"prompt_tokens": 50, "total_tokens": 2}):
            response = self.fake_response()
            response["usage"] = usage
            with self.subTest(usage=usage), self.mock_api(payload=response) as (client, _):
                with self.assertRaisesRegex(ValueError, "response failed validation"):
                    self.embed(client)

    def test_api_errors_are_sanitized_and_not_retried(self):
        for status, message in ((401, "authentication"), (429, "quota or rate"), (500, "did not complete")):
            with self.subTest(status=status), self.mock_api(
                payload={"error": {"message": "fictional-private-detail"}}, status=status,
            ) as (client, calls):
                with self.assertRaisesRegex(ValueError, message) as error:
                    self.embed(client)
                self.assertNotIn("fictional-private-detail", str(error.exception))
                self.assertEqual(len(calls), 1)
        with self.mock_api(timeout=True) as (client, calls):
            with self.assertRaisesRegex(ValueError, "may have been processed"):
                self.embed(client)
            self.assertEqual(len(calls), 1)

    def test_cli_disabled_or_missing_allowance_stops_before_reading_key(self):
        with self.command_context() as (_, _, pricing, key), patch.object(embed_example, "OpenAI") as client:
            pricing["paid_service_use_enabled"] = False
            status, output = self.run_cli(["--live", "--max-cost-usd", "0.001"])
            self.assertEqual(status, 1)
            self.assertIn("disabled", output)
            pricing["paid_service_use_enabled"] = True
            for args in (["--live"], ["--live", "--max-cost-usd", "NaN"], ["--live", "--max-cost-usd", "invalid"]):
                self.assertEqual(self.run_cli(args)[0], 1)
            key.assert_not_called()
            client.assert_not_called()

    def test_cli_rejects_ineligible_example_and_invalid_strategy(self):
        with self.command_context() as (_, settings, _, _), patch.object(embed_example, "OpenAI") as client:
            for identifier in ("SIM-1024-v1:checks:section-v1", "unknown"):
                settings["embedding_example"]["chunk_id"] = identifier
                status, output = self.run_cli([])
                self.assertEqual(status, 1)
                self.assertIn("not approved and effective", output)
            settings["chunk_preparation"]["strategy"] = "different"
            self.assertEqual(self.run_cli([])[0], 1)
            client.assert_not_called()

    def test_cli_missing_key_and_existing_or_invalid_output_never_send(self):
        with self.command_context() as (root, settings, _, key), patch.object(embed_example, "OpenAI") as client:
            key.return_value = ""
            status, output = self.run_cli(["--live", "--max-cost-usd", "0.001"])
            self.assertEqual(status, 1)
            self.assertIn("OPENAI_API_KEY is missing", output)
            existing = root / settings["embedding_example"]["output_file"]
            existing.parent.mkdir(parents=True)
            existing.write_text("prior result", encoding="utf-8")
            status, output = self.run_cli(["--live", "--max-cost-usd", "0.001"])
            self.assertEqual(status, 1)
            self.assertIn("already exists", output)
            self.assertEqual(existing.read_text(encoding="utf-8"), "prior result")
            settings["embedding_example"]["output_file"] = "data/knowledge/source.json"
            self.assertEqual(self.run_cli(["--live", "--max-cost-usd", "0.001"])[0], 1)
            client.assert_not_called()

    def test_cli_saves_simulated_result_only_in_temporary_test_folder(self):
        with self.command_context() as (root, settings, _, _), self.mock_api() as (client, calls), patch.object(
            embed_example, "OpenAI", return_value=client,
        ) as factory:
            status, output = self.run_cli(["--live", "--max-cost-usd", "0.001"])
            self.assertEqual(status, 0)
            saved = json.loads((root / settings["embedding_example"]["output_file"]).read_text(encoding="utf-8"))
            self.assertEqual(saved["chunk_id"], self.chunk.id)
            self.assertEqual(saved["metadata"], self.chunk.metadata)
            self.assertEqual(len(saved["vector"]), 1536)
            self.assertEqual(saved["as_of_date"], "2026-10-15")
            self.assertEqual(len(calls), 1)
            self.assertNotIn("fictional-private-key", output)
            self.assertNotIn("fictional-private-key", json.dumps(saved))
            self.assertEqual(factory.call_args.kwargs["max_retries"], 0)
            self.assertEqual(factory.call_args.kwargs["timeout"], 30)
            self.assertEqual(factory.call_args.kwargs["base_url"], "https://api.openai.com/v1")

    def test_cli_save_failure_explains_possible_cost_and_preserves_no_output(self):
        with self.command_context() as (root, settings, _, _), self.mock_api() as (client, calls), patch.object(
            embed_example, "OpenAI", return_value=client,
        ), patch.object(embed_example, "save_chunk_export", side_effect=OSError("fictional-private-detail")):
            status, output = self.run_cli(["--live", "--max-cost-usd", "0.001"])
            self.assertEqual(status, 1)
            self.assertIn("Usage may be billed", output)
            self.assertNotIn("fictional-private-detail", output)
            self.assertEqual(len(calls), 1)
            self.assertFalse((root / settings["embedding_example"]["output_file"]).exists())


if __name__ == "__main__":
    unittest.main()
