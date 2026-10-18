import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from langchain_core.documents import Document

from document_fixtures import replace_document as replace
from retail_copilot.documents import PROJECT_ROOT, approved_documents, load_documents


class PolicyLibraryTests(unittest.TestCase):
    def setUp(self):
        self.path = PROJECT_ROOT / "data" / "knowledge"
        self.documents = load_documents(self.path)
        self.records = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(self.path.glob("*.json"))]
        self.sim = next(item for item in self.documents if item.id == "SIM-1024-v2")
        self.as_of = date(2026, 10, 15)

    def load_modified(self, records):
        with tempfile.TemporaryDirectory() as folder:
            for position, record in enumerate(records):
                path = Path(folder) / f"document-{position}.json"
                path.write_text(json.dumps(record), encoding="utf-8")
            return load_documents(Path(folder))

    def test_approved_sources_and_metadata_are_preserved(self):
        selected = approved_documents(self.documents, self.as_of)
        self.assertEqual(len(self.documents), 12)
        self.assertEqual(len(selected), 11)
        self.assertNotIn("SIM-1024-v1", {item.id for item in selected})
        self.assertEqual(self.sim.metadata["source_file"], "SIM-1024-v2.json")
        self.assertEqual(self.sim.metadata["version"], "2")
        self.assertEqual(self.sim.metadata["sections"][0]["section_id"], "appointments")
        self.assertEqual(self.sim.metadata["review_date"], "2027-01-01")
        self.assertEqual({item.metadata["category"] for item in selected}, {
            "sim_replacement", "esim_activation", "identity_verification",
            "international_roaming", "billing_enquiries", "device_returns",
            "click_and_collect", "mobile_plans", "account_authority",
            "device_troubleshooting", "knowledge_guidance",
        })

    def test_draft_and_archived_documents_are_excluded(self):
        base = self.documents[0]
        self.assertEqual(approved_documents([
            replace(base, status="draft"), replace(base, status="archived")
        ], self.as_of), [])

    def test_effective_date_boundaries_are_inclusive(self):
        document = replace(self.sim, effective_to=date(2026, 10, 31))
        for day in (date(2026, 10, 1), date(2026, 10, 31)):
            self.assertEqual(approved_documents([document], day), [document])
        for day in (date(2026, 9, 30), date(2026, 11, 1)):
            self.assertEqual(approved_documents([document], day), [])

    def test_overlapping_approved_versions_stop_processing(self):
        document = self.sim
        competing = replace(document, document_id="SIM-1024-v3", version="3")
        with self.assertRaisesRegex(ValueError, "Conflicting approved versions"):
            approved_documents([document, competing], self.as_of)

    def test_non_synthetic_input_is_rejected(self):
        records = copy.deepcopy(self.records)
        records[0]["synthetic"] = False
        with self.assertRaisesRegex(ValueError, "marked synthetic"):
            self.load_modified(records)

    def test_duplicate_source_identifiers_are_rejected(self):
        records = copy.deepcopy(self.records)
        records.append(records[0])
        with self.assertRaisesRegex(ValueError, "IDs must be unique"):
            self.load_modified(records)

    def test_missing_citation_metadata_is_rejected(self):
        for field in ("title", "category", "customer_segment", "owner", "product", "process"):
            with self.subTest(field=field):
                records = copy.deepcopy(self.records)
                del records[0][field]
                with self.assertRaisesRegex(ValueError, "missing required text or metadata"):
                    self.load_modified(records)

    def test_invalid_date_interval_is_rejected(self):
        records = copy.deepcopy(self.records)
        records[0]["effective_to"] = "2025-01-01"
        with self.assertRaisesRegex(ValueError, "ends before it takes effect"):
            self.load_modified(records)

    def test_missing_or_invalid_dates_are_rejected(self):
        for field in ("effective_from", "review_date"):
            for value in (None, "20261001", "2026-02-30", 20261001):
                with self.subTest(field=field, value=value):
                    records = copy.deepcopy(self.records)
                    records[0][field] = value
                    with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
                        self.load_modified(records)

    def test_review_date_is_validated_but_is_not_automatic_expiry(self):
        records = copy.deepcopy(self.records)
        records[0]["review_date"] = "2025-01-01"
        with self.assertRaisesRegex(ValueError, "review date before"):
            self.load_modified(records)
        self.assertEqual(approved_documents([self.sim], date(2027, 1, 2)), [self.sim])

    def test_empty_or_incomplete_sections_are_rejected(self):
        for sections in ([], None, ["not a section"], [{"section_id": "checks", "heading": "Checks", "text": " "}]):
            with self.subTest(sections=sections):
                records = copy.deepcopy(self.records)
                records[0]["sections"] = sections
                with self.assertRaises(ValueError):
                    self.load_modified(records)

    def test_duplicate_section_ids_are_rejected(self):
        records = copy.deepcopy(self.records)
        records[0]["sections"].append(records[0]["sections"][0])
        with self.assertRaisesRegex(ValueError, "section IDs must be unique"):
            self.load_modified(records)

    def test_disclaimer_and_id_consistency_are_required(self):
        for field, value, message in (
            ("disclaimer", "Real provider policy", "fictional training disclaimer"),
            ("document_id", "invented-source", "matching policy"),
            ("version", "0", "matching policy"),
            ("status", "published", "unsupported approval status"),
        ):
            with self.subTest(field=field):
                records = copy.deepcopy(self.records)
                records[0][field] = value
                with self.assertRaisesRegex(ValueError, message):
                    self.load_modified(records)

    def test_source_filename_is_derived_not_trusted_from_document_text(self):
        records = copy.deepcopy(self.records[:1])
        records[0]["source"] = "invented-authority.pdf"
        records[0]["source_file"] = "another-invented-source.pdf"
        self.assertEqual(self.load_modified(records)[0].metadata["source_file"], "document-0.json")

    def test_empty_folder_and_invalid_json_have_clear_errors(self):
        with self.assertRaisesRegex(ValueError, "no JSON documents"):
            self.load_modified([])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "broken.json"
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "valid UTF-8 JSON"):
                load_documents(path)

    def test_archived_document_is_not_reenabled_for_a_historical_date(self):
        self.assertEqual(approved_documents(self.documents, date(2026, 9, 1)), [])

    def test_loader_returns_langchain_documents_with_serializable_policy_metadata(self):
        for document in self.documents:
            self.assertIs(type(document), Document)
            self.assertEqual(document.id, document.metadata["document_id"])
            self.assertEqual(document.page_content, "\n\n".join(
                section["text"] for section in document.metadata["sections"]
            ))
            restored = Document.model_validate_json(document.model_dump_json())
            self.assertEqual(restored, document)
            self.assertEqual(approved_documents([restored], self.as_of),
                             approved_documents([document], self.as_of))


if __name__ == "__main__":
    unittest.main()
