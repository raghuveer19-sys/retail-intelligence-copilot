"""Offline checks of bounded policy lookup; no embeddings or external requests."""

from copy import deepcopy
from datetime import date
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from pinecone import Document

from retail_copilot.documents import PROJECT_ROOT, approved_documents, load_documents, load_settings
from retail_copilot.chunking import section_chunks
from retail_copilot import policy_lookup as lookup, retrieve
from retail_copilot.pinecone_records import to_pinecone_record


SIM = "SIM-1024-v2:checks:section-v1"
AUTH = "AUTH-1001-v1:roles:section-v1"


class PolicyLookupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = load_settings()
        policies = approved_documents(load_documents(PROJECT_ROOT / "data/knowledge"), date(2026, 10, 15))
        cls.records = {}
        for policy in policies:
            for chunk in section_chunks(policy):
                record = to_pinecone_record({
                    "provider": "ollama", "model": cls.settings["embedding"]["model"], "dimensions": 768,
                    "chunk_id": chunk.id, "text": chunk.page_content,
                    "metadata": deepcopy(chunk.metadata), "vector": [0.1] * 768,
                }, cls.settings["embedding"])
                cls.records[chunk.id] = {"_id": chunk.id, **record["metadata"]}
        cls.prepared = {"documents": [{**record, "embedding": [0.1] * 768} for record in cls.records.values()]}

    def result(self, question="What checks are needed for a replacement?", ids=(SIM, AUTH)):
        hits = []
        for rank, identifier in enumerate(ids):
            fields = deepcopy(self.records[identifier])
            fields.pop("_id")
            text = fields.pop("text")
            hits.append({"chunk_id": identifier, "text": text, "metadata": fields, "score": 0.8 - rank / 10})
        return {"question": question, "matches": hits, "pinecone_read_units": 1, "total_seconds": 1.0,
                "top_k": 4, "as_of_date": "2026-10-15", "answer_generated": False, "retrieval_mode": "semantic"}

    def plan(self, result, **options):
        return lookup.plan_lookup(result, self.prepared, {**self.settings["policy_lookup"], **options}, "embedding")

    def fetch(self, **request):
        return SimpleNamespace(namespace="telecom-demo-v1", usage=SimpleNamespace(read_units=1),
                               documents={identifier: Document(deepcopy(self.records[identifier])) for identifier in request["ids"]})

    def index(self):
        index = MagicMock()
        index.documents.fetch.side_effect = self.fetch
        return index

    def test_policy_tokens_are_complete_case_insensitive_and_unique(self):
        self.assertEqual(lookup.policy_ids("sim-1024 SIM-1024, IDV-1001; XYZ-9999 SIM-10240 SIM-1024-v1"),
                         ["SIM-1024", "IDV-1001", "XYZ-9999", "SIM-10240", "SIM-1024-V1"])
        self.assertEqual(lookup.policy_ids("prefix-SIM-1024 SIM-1024x SIM-1024_extra SIM-1024-v1x"), [])

    def test_explicit_question_id_takes_precedence_over_passage_references(self):
        plan = self.plan(self.result("What does policy sim-1024 say?"))
        self.assertEqual(plan["policy_ids"], ["SIM-1024"])
        self.assertEqual(plan["requested_chunk_ids"], ["SIM-1024-v2:appointments:section-v1", "SIM-1024-v2:esim:section-v1"])
        self.assertEqual(plan["origins"]["SIM-1024"], [{"kind": "question_policy_id", "source_chunk_id": None}])

    def test_original_passages_supply_references_without_duplicate_sections(self):
        plan = self.plan(self.result())
        self.assertEqual(plan["policy_ids"], ["IDV-1001", "AUTH-1001"])
        self.assertEqual(len(plan["requested_chunk_ids"]), 5)
        self.assertNotIn(AUTH, plan["requested_chunk_ids"])
        self.assertEqual(plan["origins"]["IDV-1001"][0]["source_chunk_id"], SIM)

    def test_unknown_or_version_specific_question_does_not_fall_back_to_references(self):
        for question, field in [("XYZ-9999?", "unknown_policy_ids"), ("SIM-10240?", "unknown_policy_ids"),
                                ("SIM-1024-v1?", "unsupported_version_ids")]:
            index = self.index()
            result = lookup.follow_policy_references(index, self.result(question), self.prepared, self.settings)
            index.documents.fetch.assert_not_called()
            self.assertTrue(result["policy_lookup"][field])
            self.assertFalse(result["policy_lookup"]["lookup_complete_within_scope"])
            self.assertEqual(result["policy_lookup"]["policy_ids"], [])

    def test_excluded_policy_is_not_fetched_from_unapproved_local_sources(self):
        prepared = deepcopy(self.prepared)
        prepared["documents"] = [doc for doc in prepared["documents"] if doc["policy_id"] != "IDV-1001"]
        result = lookup.follow_policy_references(self.index(), self.result("IDV-1001?"), prepared, self.settings)
        self.assertEqual(result["policy_lookup"]["unknown_policy_ids"], ["IDV-1001"])
        self.assertEqual(result["policy_lookup"]["added_chunks"], 0)

    def test_limits_skip_whole_policies_without_partial_sections(self):
        plan = self.plan(self.result(), max_added_chunks=2)
        self.assertEqual(plan["skipped_policy_ids"], ["IDV-1001"])
        self.assertEqual(plan["policy_ids"], ["AUTH-1001"])
        self.assertEqual(len(plan["requested_chunk_ids"]), 2)
        plan = self.plan(self.result(), max_policies=1)
        self.assertEqual(plan["policy_ids"], ["IDV-1001"])
        self.assertEqual(plan["skipped_policy_ids"], ["AUTH-1001"])

    def test_invalid_limits_and_modified_seeds_stop_before_fetch(self):
        for options in [{"max_policies": 0}, {"max_policies": True}, {"max_added_chunks": 13}]:
            with self.assertRaises(lookup.PolicyLookupError):
                self.plan(self.result(), **options)
        for change in ("text", "duplicate", "metadata"):
            result = self.result()
            if change == "text":
                result["matches"][0]["text"] = "changed"
            elif change == "metadata":
                result["matches"][0]["metadata"]["status"] = "archived"
            else:
                result["matches"].append(deepcopy(result["matches"][0]))
            index = self.index()
            with self.assertRaises(lookup.PolicyLookupError):
                lookup.follow_policy_references(index, result, self.prepared, self.settings)
            index.documents.fetch.assert_not_called()

    def test_fetch_preserves_scores_sources_and_input_and_does_not_recurse(self):
        original = self.result("SIM-1024?", ids=(SIM,))
        before = deepcopy(original)
        index = self.index()
        result = lookup.follow_policy_references(index, original, self.prepared, self.settings)
        self.assertEqual(original, before)
        self.assertEqual(result["matches"][0]["score"], 0.8)
        self.assertEqual(result["matches"][0]["semantic_rank"], 1)
        self.assertEqual(result["semantic_match_count"], 1)
        self.assertEqual(len(result["matches"]), 3)
        self.assertEqual({hit["metadata"]["policy_id"] for hit in result["matches"]}, {"SIM-1024"})
        for hit in result["matches"][1:]:
            self.assertIsNone(hit["score"])
            self.assertIsNone(hit["semantic_rank"])
            self.assertEqual(hit["retrieval_method"], "policy_lookup")
            self.assertEqual(hit["metadata"]["source_file"], "SIM-1024-v2.json")
        request = index.documents.fetch.call_args.kwargs
        self.assertNotIn("embedding", request["include_fields"])
        self.assertIn("source_file", request["include_fields"])
        self.assertEqual(request["namespace"], "telecom-demo-v1")
        self.assertEqual(request["timeout"], 30)
        self.assertEqual(result["search_read_units"], 1)
        self.assertEqual(result["pinecone_read_units"], 2)
        self.assertEqual(result["evidence_status"], "candidates_require_review")
        self.assertFalse(result["answer_generated"])
        with self.assertRaises(lookup.PolicyLookupError):
            lookup.follow_policy_references(index, result, self.prepared, self.settings)
        self.assertEqual(index.documents.fetch.call_count, 1)

    def test_absent_references_or_complete_policy_need_no_fetch(self):
        ids = tuple(identifier for identifier in self.records if identifier.startswith("SIM-1024"))
        for original in [self.result("SIM-1024?", ids=ids), self.result("Unknown guidance?", ids=())]:
            index = self.index()
            result = lookup.follow_policy_references(index, original, self.prepared, self.settings)
            index.documents.fetch.assert_not_called()
            self.assertEqual(result["pinecone_read_units"], 1)
            self.assertEqual(result["policy_lookup"]["fetch_read_units"], 0)
        self.assertEqual(result["evidence_status"], "no_candidates")

    def test_missing_extra_changed_or_wrong_namespace_fetch_rejected(self):
        original = self.result("SIM-1024?", ids=(SIM,))
        for change in ("missing", "extra", "text", "metadata", "namespace"):
            response = self.fetch(ids=self.plan(original)["requested_chunk_ids"])
            identifier = next(iter(response.documents))
            if change == "missing":
                response.documents.pop(identifier)
            elif change == "extra":
                response.documents[SIM] = Document(self.records[SIM])
            elif change == "namespace":
                response.namespace = "other"
            else:
                fields = response.documents[identifier].to_dict()
                fields["text" if change == "text" else "source_file"] = "changed"
                response.documents[identifier] = Document(fields)
            index = MagicMock()
            index.documents.fetch.return_value = response
            with self.subTest(change=change), self.assertRaises(lookup.PolicyLookupError):
                lookup.follow_policy_references(index, original, self.prepared, self.settings)

    def test_missing_usage_is_unknown_and_invalid_usage_is_rejected(self):
        original = self.result("SIM-1024?", ids=(SIM,))
        response = self.fetch(ids=self.plan(original)["requested_chunk_ids"])
        index = MagicMock()
        index.documents.fetch.return_value = response
        response.usage = None
        result = lookup.follow_policy_references(index, original, self.prepared, self.settings)
        self.assertIsNone(result["pinecone_read_units"])
        for units in (-1, True, float("nan")):
            response.usage = SimpleNamespace(read_units=units)
            with self.assertRaises(lookup.PolicyLookupError):
                lookup.follow_policy_references(index, original, self.prepared, self.settings)

    def test_expanded_recall_is_not_mislabelled_recall_at_four(self):
        case = retrieve.baseline_cases(PROJECT_ROOT, self.settings)[2]
        original = self.result(case["user_question"], ids=(SIM,))
        result = lookup.follow_policy_references(self.index(), original, self.prepared, self.settings)
        score = retrieve.score_expected_sources(result, case)
        self.assertIsNone(score["expected_source_recall_at_k"])
        self.assertEqual(score["expected_source_recall"], 1)
        self.assertEqual(score["measurement_scope"], "semantic_plus_policy_lookup")
        self.assertIsNone(score["answer_groundedness"])


if __name__ == "__main__":
    unittest.main()
