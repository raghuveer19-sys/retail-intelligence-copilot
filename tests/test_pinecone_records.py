"""Local format checks with dummy vectors: no Pinecone or embedding requests."""

from copy import deepcopy
from datetime import date
import json
import unittest
from unittest.mock import patch

from retail_copilot.chunking import section_chunks
from retail_copilot.documents import PROJECT_ROOT, approved_documents, load_documents, load_settings
from retail_copilot.pinecone_records import MAX_METADATA_BYTES, SOURCE_FIELDS, to_pinecone_record


class PineconeRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = load_settings()
        cls.embedding = cls.settings["embedding"]
        documents = load_documents(PROJECT_ROOT / cls.settings["demo"]["knowledge_directory"])
        eligible = approved_documents(documents, date.fromisoformat(cls.settings["demo"]["as_of_date"]))
        cls.chunks = [chunk for document in eligible for chunk in section_chunks(document)]

    def result_for(self, chunk=None):
        chunk = self.chunks[0] if chunk is None else chunk
        return {
            "provider": self.embedding["provider"], "model": self.embedding["model"],
            "dimensions": self.embedding["dimensions"], "chunk_id": chunk.id,
            "text": chunk.page_content, "metadata": deepcopy(chunk.metadata),
            # Deliberately meaningless fixture, never written or uploaded.
            "vector": [0.1] * self.embedding["dimensions"],
            "usage": {"prompt_tokens": 50, "total_tokens": 50},
            "pre_request_estimate_usd": "0.00000100",
        }

    def test_all_eligible_chunks_keep_exact_text_and_source_without_network(self):
        records = []
        with patch("socket.socket.connect", side_effect=AssertionError("Unexpected network call")):
            for chunk in self.chunks:
                record = to_pinecone_record(self.result_for(chunk), self.embedding)
                self.assertEqual(set(record), {"id", "values", "metadata"})
                self.assertEqual(record["id"], chunk.id)
                self.assertEqual(record["metadata"]["text"], chunk.page_content)
                for field in SOURCE_FIELDS:
                    self.assertEqual(record["metadata"][field], chunk.metadata[field])
                self.assertNotIn("usage", record["metadata"])
                self.assertNotIn("pre_request_estimate_usd", record["metadata"])
                self.assertNotIn("SIM-1024-v1:", record["id"])
                json.dumps(record, allow_nan=False)
                records.append(record)
        self.assertEqual(len(records), 33)
        self.assertEqual(len({record["id"] for record in records}), 33)

    def test_optional_null_is_omitted_and_output_is_independent(self):
        result = self.result_for()
        result["metadata"].update(effective_to=None, tags=["fictional"])
        before = deepcopy(result)
        record = to_pinecone_record(result, self.embedding)
        self.assertNotIn("effective_to", record["metadata"])
        record["values"][0] = 7
        record["metadata"]["tags"].append("changed")
        self.assertEqual(result, before)

    def test_missing_source_details_are_rejected(self):
        for field in SOURCE_FIELDS:
            with self.subTest(field=field):
                result = self.result_for()
                result["metadata"][field] = None
                with self.assertRaisesRegex(ValueError, field):
                    to_pinecone_record(result, self.embedding)

    def test_model_and_dimension_mismatches_are_rejected(self):
        for field, value in (("provider", "different"), ("model", "different"), ("dimensions", 8), ("dimensions", True)):
            with self.subTest(field=field, value=value):
                result = self.result_for()
                result[field] = value
                with self.assertRaises(ValueError):
                    to_pinecone_record(result, self.embedding)

    def test_missing_or_invalid_vector_is_rejected(self):
        size = self.embedding["dimensions"]
        for vector in (None, [], [0.1] * (size - 1), [0] * size,
                       [True] * size, [float("nan")] * size, [float("inf")] * size):
            with self.subTest(first=None if not vector else vector[0]):
                result = self.result_for()
                result["vector"] = vector
                with self.assertRaises(ValueError):
                    to_pinecone_record(result, self.embedding)

    def test_invalid_metadata_types_and_keys_are_rejected(self):
        for key, value in (("nested", {"a": "b"}), ("numbers", [1, 2]),
                           ("invalid", float("nan")), ("$field", "value"), (1, "value")):
            with self.subTest(key=key):
                result = self.result_for()
                result["metadata"][key] = value
                with self.assertRaises(ValueError):
                    to_pinecone_record(result, self.embedding)

    def test_text_and_identifier_collisions_are_rejected(self):
        for field, value in (("text", "different passage"), ("chunk_id", "different-id")):
            with self.subTest(field=field):
                result = self.result_for()
                result["metadata"][field] = value
                with self.assertRaises(ValueError):
                    to_pinecone_record(result, self.embedding)

    def test_metadata_limit_counts_utf8_bytes_including_passage(self):
        result = self.result_for()
        result["text"] = ""
        baseline = to_pinecone_record({**result, "text": "x"}, self.embedding)
        overhead = len(json.dumps(baseline["metadata"], ensure_ascii=False).encode("utf-8")) - 1
        result["text"] = "x" * (MAX_METADATA_BYTES - overhead)
        to_pinecone_record(result, self.embedding)  # Boundary allowed.
        result["text"] += "x"
        with self.assertRaisesRegex(ValueError, "40,000-byte"):
            to_pinecone_record(result, self.embedding)
        result["text"] = "界" * 15_000  # Fewer characters, more bytes.
        with self.assertRaisesRegex(ValueError, "40,000-byte"):
            to_pinecone_record(result, self.embedding)

    def test_required_input_and_configuration_fail_clearly(self):
        for field, value in (("text", " "), ("chunk_id", ""), ("metadata", None)):
            result = self.result_for()
            result[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                to_pinecone_record(result, self.embedding)
        for dimensions in (None, True, 0, -1):
            with self.subTest(dimensions=dimensions), self.assertRaises(ValueError):
                to_pinecone_record(self.result_for(), {**self.embedding, "dimensions": dimensions})


if __name__ == "__main__":
    unittest.main()
