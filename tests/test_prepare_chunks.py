import copy
import io
import json
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
from datetime import date
from pathlib import Path
from unittest.mock import patch

from document_fixtures import replace_document as replace
from retail_copilot import prepare_chunks
from retail_copilot.documents import PROJECT_ROOT, load_documents, load_settings


class PrepareChunksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = load_documents(PROJECT_ROOT / "data" / "knowledge")
        cls.as_of = date(2026, 10, 15)
        cls.authority = next(doc for doc in cls.library if doc.id == "AUTH-1001-v1")

    def build(self, documents=None, as_of=None):
        return prepare_chunks.build_chunk_export(
            self.library if documents is None else documents,
            self.as_of if as_of is None else as_of, "section-v1",
        )

    @contextmanager
    def local_project(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            knowledge = root / "data" / "knowledge"
            knowledge.mkdir(parents=True)
            for source in (PROJECT_ROOT / "data" / "knowledge").glob("*.json"):
                (knowledge / source.name).write_bytes(source.read_bytes())
            settings = copy.deepcopy(load_settings())
            with patch.object(prepare_chunks, "PROJECT_ROOT", root), patch.object(
                prepare_chunks, "load_settings", return_value=settings,
            ):
                yield root, settings

    def test_export_preserves_every_eligible_section_and_source_field(self):
        export = self.build()
        self.assertEqual(export["loaded_documents"], 12)
        self.assertEqual(export["eligible_documents"], 11)
        self.assertEqual(export["excluded_document_ids"], ["SIM-1024-v1"])
        self.assertEqual(export["chunk_count"], 33)
        self.assertEqual(len(export["chunks"]), 33)
        self.assertEqual(len({item["chunk_id"] for item in export["chunks"]}), 33)
        for record in export["chunks"]:
            metadata = record["metadata"]
            source = PROJECT_ROOT / "data" / "knowledge" / metadata["source_file"]
            original = json.loads(source.read_text(encoding="utf-8"))
            sections = original.pop("sections")
            section = next(item for item in sections if item["section_id"] == metadata["section_id"])
            self.assertEqual(record["text"], section["text"])
            self.assertEqual(record["word_count"], len(section["text"].split()))
            original["document_title"] = original.pop("title")
            original.update(source_file=source.name, section_id=section["section_id"],
                            section_heading=section["heading"])
            self.assertEqual(metadata, original)

    def test_reruns_and_input_reordering_produce_identical_exports(self):
        expected = self.build()
        reordered = [replace(doc, sections=list(reversed(doc.metadata["sections"]))) for doc in reversed(self.library)]
        self.assertEqual(self.build(), expected)
        self.assertEqual(self.build(reordered), expected)

    def test_ids_identify_sections_and_versions_instead_of_text_contents(self):
        original = self.build([self.authority])["chunks"]
        self.assertIn("AUTH-1001-v1:delegation:section-v1", {item["chunk_id"] for item in original})
        changed = replace(self.authority, sections=[
            {**section, "text": section["text"] + " Fictional clarification."}
            for section in self.authority.metadata["sections"]
        ])
        edited = self.build([changed])["chunks"]
        self.assertEqual([item["chunk_id"] for item in original], [item["chunk_id"] for item in edited])
        self.assertNotEqual([item["text"] for item in original], [item["text"] for item in edited])
        revised = replace(changed, document_id="AUTH-1001-v2", version="2")
        self.assertTrue({item["chunk_id"] for item in original}.isdisjoint(
            item["chunk_id"] for item in self.build([revised])["chunks"]
        ))

    def test_ineligible_documents_never_produce_records(self):
        for change in (
            {"status": "draft"}, {"status": "archived"},
            {"effective_from": date(2026, 11, 1)}, {"effective_to": date(2026, 10, 14)},
        ):
            with self.subTest(change=change):
                documents = [replace(doc, **change) if doc == self.authority else doc for doc in self.library]
                export = self.build(documents)
                self.assertIn(self.authority.id, export["excluded_document_ids"])
                self.assertFalse(any(item["metadata"]["policy_id"] == "AUTH-1001" for item in export["chunks"]))

    def test_empty_eligible_set_and_overlapping_versions_stop_preparation(self):
        for documents in ([], [replace(self.authority, status="archived")]):
            with self.assertRaisesRegex(ValueError, "No approved, effective policies"):
                self.build(documents)
        with self.assertRaisesRegex(ValueError, "Conflicting approved versions"):
            self.build([self.authority, replace(self.authority, document_id="AUTH-1001-v2", version="2")])

    def test_unsupported_strategy_and_duplicate_chunk_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "supports strategy"):
            prepare_chunks.build_chunk_export(self.library, self.as_of, "guess")
        duplicate = replace(self.authority, sections=[self.authority.metadata["sections"][0]] * 2)
        with self.assertRaisesRegex(ValueError, "Duplicate chunk ID"):
            self.build([duplicate])

    def test_long_section_and_unicode_are_preserved_without_truncation(self):
        text = "Fictional caf\u00e9 guidance.\n\n" + " ".join(f"condition{i}" for i in range(2000))
        document = replace(self.authority, sections=[{**self.authority.metadata["sections"][0], "text": text}])
        export = self.build([document])
        self.assertEqual(len(export["chunks"]), 1)
        self.assertEqual(export["chunks"][0]["text"], text)
        self.assertEqual(json.loads(json.dumps(export))["chunks"][0]["text"], text)

    def test_saved_rerun_is_identical_and_replaces_removed_sections(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "chunks.json"
            prepare_chunks.save_chunk_export(self.build(), output)
            previous = output.read_bytes()
            prepare_chunks.save_chunk_export(self.build(), output)
            self.assertEqual(output.read_bytes(), previous)
            reduced = self.build([replace(self.authority, sections=self.authority.metadata["sections"][:1])])
            prepare_chunks.save_chunk_export(reduced, output)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), reduced)
            self.assertEqual(list(output.parent.glob("*.tmp")), [])

    def test_failed_replacement_preserves_previous_export_and_cleans_temporary_file(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "chunks.json"
            output.write_text("previous complete export", encoding="utf-8")
            with patch.object(Path, "replace", side_effect=OSError("file is locked")):
                with self.assertRaisesRegex(OSError, "file is locked"):
                    prepare_chunks.save_chunk_export(self.build(), output)
            self.assertEqual(output.read_text(encoding="utf-8"), "previous complete export")
            self.assertEqual(list(output.parent.glob("*.tmp")), [])

    def test_command_loads_real_files_and_saves_the_snapshot(self):
        with self.local_project() as (root, settings), redirect_stdout(io.StringIO()) as messages:
            self.assertEqual(prepare_chunks.main(), 0)
            output = root / settings["chunk_preparation"]["output_file"]
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), self.build())
        self.assertIn("Saved 33 chunks", messages.getvalue())
        self.assertIn("no API calls", messages.getvalue())

    def test_command_failure_leaves_previous_output_and_explains_it(self):
        with self.local_project() as (root, settings):
            output = root / settings["chunk_preparation"]["output_file"]
            output.parent.mkdir(parents=True)
            output.write_text("previous complete export", encoding="utf-8")
            settings["demo"]["as_of_date"] = "2026-09-01"
            with redirect_stdout(io.StringIO()) as messages:
                self.assertEqual(prepare_chunks.main(), 1)
            self.assertIn("No approved, effective policies", messages.getvalue())
            self.assertIn("Do not use an earlier export", messages.getvalue())
            self.assertEqual(output.read_text(encoding="utf-8"), "previous complete export")

    def test_command_rejects_output_outside_generated_folder_and_missing_settings(self):
        with self.local_project() as (root, settings):
            source = root / "data" / "knowledge" / "SIM-1024-v2.json"
            previous = source.read_bytes()
            for destination in ("data/knowledge/SIM-1024-v2.json", "data/processed/../knowledge/SIM-1024-v2.json", "data/processed/chunks.txt"):
                settings["chunk_preparation"]["output_file"] = destination
                with redirect_stdout(io.StringIO()) as messages:
                    self.assertEqual(prepare_chunks.main(), 1)
                self.assertIn("inside data/processed/", messages.getvalue())
                self.assertEqual(source.read_bytes(), previous)
            del settings["chunk_preparation"]
            with redirect_stdout(io.StringIO()) as messages:
                self.assertEqual(prepare_chunks.main(), 1)
            self.assertIn("check demo and chunk_preparation", messages.getvalue())


if __name__ == "__main__":
    unittest.main()
