"""Check the evaluation specification; these are not model-quality tests."""

import json
import unittest
from datetime import date

from retail_copilot.documents import PROJECT_ROOT, approved_documents, load_documents


class EvaluationSpecificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = json.loads((PROJECT_ROOT / "evaluation" / "cases.json").read_text(encoding="utf-8"))
        cls.documents = load_documents(PROJECT_ROOT / "data" / "knowledge")
        cls.by_id = {item.id: item for item in cls.documents}

    def test_cases_have_unique_ids_coverage_and_unmeasured_results(self):
        self.assertEqual(len(self.cases), 15)
        self.assertEqual(len({item["test_id"] for item in self.cases}), 15)
        self.assertEqual({item["category"] for item in self.cases}, {
            "direct", "paraphrased", "cross_document", "exact_identifier", "ambiguous",
            "unsupported", "action_request", "outdated_or_conflicting",
        })
        for case in self.cases:
            with self.subTest(test_id=case["test_id"]):
                for field in ("user_question", "expected_behaviour", "reference_answer", "notes"):
                    self.assertTrue(case[field].strip())
                for field in ("must_include", "must_not_include"):
                    self.assertTrue(case[field])
                    self.assertTrue(all(isinstance(value, str) and value.strip() for value in case[field]))
                for field in ("retrieval_success", "answer_groundedness", "citation_correctness"):
                    self.assertIsNone(case[field], "No live evaluation has run yet")

    def test_references_point_to_eligible_real_documents_and_sections(self):
        for case in self.cases:
            with self.subTest(test_id=case["test_id"]):
                eligible = {item.id for item in approved_documents(self.documents, date.fromisoformat(case["as_of_date"]))}
                for source in case["expected_source"]:
                    self.assertIn(source["document_id"], eligible)
                    document = self.by_id[source["document_id"]]
                    self.assertIn(source["section_id"], {item["section_id"] for item in document.metadata["sections"]})
                    self.assertTrue((PROJECT_ROOT / "data" / "knowledge" / document.metadata["source_file"]).is_file())
                for excluded in case["excluded_document_ids"]:
                    self.assertIn(excluded, self.by_id)
                    self.assertNotIn(excluded, eligible)

    def test_missing_authority_case_uses_a_deliberately_restricted_context(self):
        case = next(item for item in self.cases if item["test_id"] == "E11")
        self.assertEqual(case["evaluation_mode"], "controlled_context")
        self.assertEqual(case["context_document_ids"], ["SIM-1024-v2"])
        self.assertNotIn("AUTH-1001-v1", case["context_document_ids"])
        for source in case["expected_source"]:
            self.assertIn(source["document_id"], case["context_document_ids"])


if __name__ == "__main__":
    unittest.main()
