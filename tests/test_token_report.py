import copy
import io
import unittest
from contextlib import redirect_stdout
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from langchain_core.documents import Document

from document_fixtures import replace_document
from retail_copilot import token_report
from retail_copilot.chunking import section_chunks
from retail_copilot.documents import PROJECT_ROOT, approved_documents, load_documents, load_settings
from retail_copilot.prepare_chunks import build_chunk_export


class TokenReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = load_settings()
        cls.embedding = cls.settings["openai_embedding"]
        cls.pricing = token_report.load_pricing(PROJECT_ROOT / "config" / "pricing.yaml")
        cls.encoding = token_report.load_tokenizer(cls.embedding)
        cls.library = load_documents(PROJECT_ROOT / "data" / "knowledge")

    def report(self, texts, embedding=None, pricing=None):
        chunks = [Document(id=f"example-{i}", page_content=text) for i, text in enumerate(texts)]
        return token_report.build_token_report(
            chunks, self.embedding if embedding is None else embedding,
            self.pricing if pricing is None else pricing,
        )

    def run_command(self, settings=None, documents=None):
        with patch.object(token_report, "load_settings", return_value=self.settings if settings is None else settings), patch.object(
            token_report, "load_documents", return_value=self.library if documents is None else documents,
        ), redirect_stdout(io.StringIO()) as output:
            status = token_report.main()
        return status, output.getvalue()

    def test_known_tokenizer_example_is_not_a_word_count(self):
        text = "tiktoken is great!"
        self.assertEqual(len(text.split()), 3)
        self.assertEqual(token_report.count_tokens(text, self.encoding), 6)

    def test_unicode_whitespace_and_special_looking_text_are_preserved(self):
        text = "  Fictional café guidance.\n\n你好 <|endoftext|>  "
        chunk = Document(id="example", page_content=text, metadata={"source_file": "fictional.json"})
        before = copy.deepcopy(chunk.model_dump())
        report = token_report.build_token_report([chunk], self.embedding, self.pricing)
        encoded = self.encoding.encode(text, disallowed_special=())
        self.assertEqual(self.encoding.decode(encoded), text)
        self.assertEqual(report["total_tokens"], len(encoded))
        self.assertEqual(chunk.model_dump(), before)

    def test_empty_and_whitespace_only_text_are_rejected(self):
        for text in ("", " \n\t", None):
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, "non-empty text"):
                token_report.count_tokens(text, self.encoding)

    def test_exact_limit_passes_and_one_extra_token_is_flagged_without_truncation(self):
        exact = "hello" + " hello" * 8191
        larger = exact + " hello"
        report = self.report([exact, larger])
        self.assertEqual([row["token_count"] for row in report["chunks"]], [8192, 8193])
        self.assertEqual([row["within_limit"] for row in report["chunks"]], [True, False])
        self.assertFalse(report["all_within_limit"])
        self.assertEqual(report["total_tokens"], 16385)

    def test_model_and_encoding_mismatches_do_not_silently_fall_back(self):
        for changes in (
            {"provider": "different"}, {"model": "unknown-model"},
            {"tokenizer_encoding": "o200k_base"},
        ):
            with self.subTest(changes=changes), patch.object(token_report.tiktoken, "get_encoding") as fetch:
                with self.assertRaises(ValueError):
                    token_report.load_tokenizer({**self.embedding, **changes})
                fetch.assert_not_called()

    def test_invalid_limits_are_rejected(self):
        for limit in (0, -1, True, 2.5, "8192"):
            with self.subTest(limit=limit), self.assertRaisesRegex(ValueError, "positive whole number"):
                self.report(["hello"], embedding={**self.embedding, "max_input_tokens": limit})

    def test_empty_chunks_missing_ids_and_duplicate_ids_are_rejected(self):
        for chunks in (
            [], [Document(page_content="hello")], [Document(id=" ", page_content="hello")],
            [Document(id="same", page_content="hello"), Document(id="same", page_content="world")],
        ):
            with self.subTest(chunks=chunks), self.assertRaises(ValueError):
                token_report.build_token_report(chunks, self.embedding, self.pricing)

    def test_one_token_cost_keeps_precision_and_uses_configured_rate(self):
        pricing = copy.deepcopy(self.pricing)
        pricing["openai_candidates"]["embedding"]["usd_per_million_input_tokens"] = "0.02"
        result = self.report(["hello"], pricing=pricing)
        self.assertEqual(result["total_tokens"], 1)
        self.assertEqual(result["estimated_usd"], Decimal("0.00000002"))
        pricing["openai_candidates"]["embedding"]["usd_per_million_input_tokens"] = "0.04"
        self.assertEqual(self.report(["hello"], pricing=pricing)["estimated_usd"], Decimal("0.00000004"))

    def test_unknown_or_invalid_rates_never_become_a_free_estimate(self):
        for rate in (None, 0, -1, True, "unknown", "NaN", "Infinity"):
            pricing = copy.deepcopy(self.pricing)
            pricing["openai_candidates"]["embedding"]["usd_per_million_input_tokens"] = rate
            with self.subTest(rate=rate), self.assertRaises(ValueError):
                self.report(["hello"], pricing=pricing)

    def test_pricing_requires_matching_model_currency_billing_date_and_source(self):
        for field, value in (
            ("model", "other-model"), ("billing_mode", "batch"),
            ("checked_on", "unknown"), ("source", ""),
        ):
            pricing = copy.deepcopy(self.pricing)
            pricing["openai_candidates"]["embedding"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.report(["hello"], pricing=pricing)
        for pricing in ({}, {**self.pricing, "currency": "AUD"}):
            with self.assertRaises(ValueError):
                self.report(["hello"], pricing=pricing)

    def test_invalid_pricing_file_has_a_plain_language_error(self):
        for contents in ("[broken yaml", "42", "- a list"):
            with patch.object(token_report.Path, "read_text", return_value=contents):
                with self.assertRaisesRegex(ValueError, "pricing.yaml"):
                    token_report.load_pricing(PROJECT_ROOT / "config" / "pricing.yaml")

    def test_full_corpus_matches_prepared_text_and_excludes_archive(self):
        as_of = date(2026, 10, 15)
        chunks = [chunk for doc in approved_documents(self.library, as_of) for chunk in section_chunks(doc)]
        report = token_report.build_token_report(chunks, self.embedding, self.pricing)
        export = build_chunk_export(self.library, as_of, "section-v1")
        self.assertEqual(len(report["chunks"]), 33)
        self.assertEqual(sum(row["word_count"] for row in report["chunks"]), 1169)
        self.assertTrue(report["all_within_limit"])
        for measured, saved in zip(report["chunks"], export["chunks"], strict=True):
            self.assertEqual(measured["chunk_id"], saved["chunk_id"])
            self.assertFalse(measured["chunk_id"].startswith("SIM-1024-v1:"))
            self.assertEqual(measured["token_count"], token_report.count_tokens(saved["text"], self.encoding))

    def test_command_runs_without_network_after_tokenizer_is_cached(self):
        with patch("socket.socket.connect", side_effect=AssertionError("Network call attempted")):
            status, output = self.run_command()
        self.assertEqual(status, 0)
        self.assertIn("Measured 33 chunks", output)
        self.assertIn("no embedding or Pinecone API calls", output)
        self.assertIn("Estimate only, not a bill", output)
        self.assertIn("No vectors generated", output)

    def test_command_stops_for_oversized_chunk_and_keeps_its_full_count(self):
        authority = next(doc for doc in self.library if doc.id == "AUTH-1001-v1")
        oversized = replace_document(authority, sections=[{
            "section_id": "long", "heading": "Fictional long section",
            "text": "hello" + " hello" * 8192,
        }])
        status, output = self.run_command(documents=[oversized])
        self.assertEqual(status, 1)
        self.assertIn("8193 | OVER LIMIT", output)
        self.assertIn("no text was truncated", output)

    def test_command_rejects_empty_eligible_set_and_conflicting_versions(self):
        settings = copy.deepcopy(self.settings)
        settings["demo"]["as_of_date"] = "2026-09-01"
        status, output = self.run_command(settings=settings)
        self.assertEqual(status, 1)
        self.assertIn("no eligible chunks", output)
        authority = next(doc for doc in self.library if doc.id == "AUTH-1001-v1")
        status, output = self.run_command(documents=[
            authority, replace_document(authority, document_id="AUTH-1001-v2", version="2"),
        ])
        self.assertEqual(status, 1)
        self.assertIn("Conflicting approved versions", output)

    def test_command_explains_tokenizer_download_failure_without_raw_error(self):
        with patch.object(token_report.tiktoken, "get_encoding", side_effect=OSError("private detail")):
            status, output = self.run_command()
        self.assertEqual(status, 1)
        self.assertIn("First use needs internet access", output)
        self.assertNotIn("private detail", output)


if __name__ == "__main__":
    unittest.main()
