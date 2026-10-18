import copy
import io
import unittest
from contextlib import redirect_stdout
from datetime import date
from unittest.mock import patch

from langchain_core.documents import Document

from document_fixtures import replace_document as replace
from retail_copilot import chunking
from retail_copilot.documents import PROJECT_ROOT, approved_documents, load_documents, load_settings


class ChunkingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library = load_documents(PROJECT_ROOT / "data" / "knowledge")
        cls.document = next(item for item in cls.library if item.id == "AUTH-1001-v1")
        cls.section = next(item for item in cls.document.metadata["sections"] if item["section_id"] == "delegation")

    def with_text(self, text):
        return replace(self.document, sections=[{**self.section, "text": text}])

    def test_known_teaching_example_matches_observed_counts(self):
        variants = chunking.compare_section(self.document, "delegation", 20, 5)
        self.assertEqual(
            [[len(chunk.page_content.split()) for chunk in chunks] for chunks in variants.values()],
            [[20, 20, 3], [20, 20, 13], [43]],
        )
        complete_rule = self.section["text"].split(". ", 1)[0] + "."
        self.assertEqual(
            [any(complete_rule in item.page_content for item in chunks) for chunks in variants.values()],
            [False, False, True],
        )

    def test_windows_preserve_words_and_overlap_for_different_lengths(self):
        for length in (1, 19, 20, 21, 35, 40, 43, 100):
            words = [f"word{index}" for index in range(length)]
            for overlap in (0, 5, 19):
                with self.subTest(length=length, overlap=overlap):
                    chunks = chunking.fixed_size_chunks(self.with_text(" ".join(words)), 20, overlap)
                    covered = set()
                    for chunk in chunks:
                        start, end = chunk.metadata["first_word"] - 1, chunk.metadata["last_word"]
                        self.assertEqual(chunk.page_content.split(), words[start:end])
                        self.assertGreater(len(chunk.page_content.split()), 0)
                        self.assertLessEqual(len(chunk.page_content.split()), 20)
                        covered.update(range(start, end))
                    self.assertEqual(covered, set(range(length)))
                    for previous, current in zip(chunks, chunks[1:]):
                        self.assertEqual(previous.metadata["last_word"] - current.metadata["first_word"] + 1, overlap)
                        self.assertGreater(current.metadata["last_word"], previous.metadata["last_word"])
                    self.assertEqual(chunks[-1].metadata["last_word"], length)

    def test_exact_final_window_does_not_create_an_overlap_only_tail(self):
        for length, expected in ((20, 1), (35, 2), (50, 3)):
            with self.subTest(length=length):
                document = self.with_text(" ".join(f"word{i}" for i in range(length)))
                self.assertEqual(len(chunking.fixed_size_chunks(document, 20, 5)), expected)

    def test_all_eligible_sections_keep_their_source_metadata_and_words(self):
        eligible = approved_documents(self.library, date(2026, 10, 15))
        for document in eligible:
            variants = (
                chunking.fixed_size_chunks(document, 20, 0),
                chunking.fixed_size_chunks(document, 20, 5),
                chunking.section_chunks(document),
            )
            for chunks in variants:
                for section in document.metadata["sections"]:
                    selected = [item for item in chunks if item.metadata["section_id"] == section["section_id"]]
                    words = section["text"].split()
                    covered = set()
                    self.assertTrue(selected)
                    for chunk in selected:
                        self.assertIs(type(chunk), Document)
                        for key, value in document.metadata.items():
                            if key != "sections":
                                self.assertEqual(chunk.metadata[key], value)
                        self.assertNotIn("sections", chunk.metadata)
                        self.assertEqual(chunk.metadata["section_heading"], section["heading"])
                        self.assertTrue((PROJECT_ROOT / "data" / "knowledge" / chunk.metadata["source_file"]).is_file())
                        first, last = chunk.metadata["first_word"], chunk.metadata["last_word"]
                        self.assertEqual(chunk.page_content.split(), words[first - 1:last])
                        covered.update(range(first - 1, last))
                    self.assertEqual(covered, set(range(len(words))))

    def test_complete_section_preserves_long_text_without_a_hidden_size_limit(self):
        text = "A fictional rule.\n\n" + " ".join(f"condition{i}" for i in range(120))
        chunks = chunking.section_chunks(self.with_text(text))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].page_content, text)
        self.assertGreater(len(chunks[0].page_content.split()), 20)

    def test_fixed_windows_normalise_whitespace_without_changing_words(self):
        document = self.with_text("  ONLY\twhen\nverified,  do\nnot\tproceed.  ")
        chunks = chunking.fixed_size_chunks(document, 3, 0)
        self.assertEqual([item.page_content for item in chunks], ["ONLY when verified,", "do not proceed."])

    def test_chunk_metadata_is_independent_of_source_and_siblings(self):
        document = replace(self.document, learning_notes={"labels": ["original"]})
        for chunks in (chunking.section_chunks(document), chunking.fixed_size_chunks(document, 20, 5)):
            with self.subTest(first_id=chunks[0].id):
                before = copy.deepcopy(document.metadata)
                sibling = copy.deepcopy(chunks[1].metadata)
                chunks[0].metadata["learning_notes"]["labels"].append("changed")
                chunks[0].metadata["source_file"] = "changed.json"
                self.assertEqual(document.metadata, before)
                self.assertEqual(chunks[1].metadata, sibling)
        whole = chunking.section_chunks(document)
        self.assertEqual(len({item.id for item in whole}), len(whole))
        self.assertIn("AUTH-1001-v1:delegation:section-v1", {item.id for item in whole})

    def test_invalid_sizes_and_overlap_are_rejected(self):
        for size, overlap in ((0, 0), (-1, 0), (2.5, 0), (True, 0), (20, -1), (20, 20), (20, 21), (20, 1.5), (20, False)):
            with self.subTest(size=size, overlap=overlap):
                with self.assertRaises(ValueError):
                    chunking.fixed_size_chunks(self.document, size, overlap)

    def test_empty_sections_are_rejected(self):
        document = self.with_text(" \n\t")
        with self.assertRaisesRegex(ValueError, "must contain text"):
            chunking.fixed_size_chunks(document, 20, 5)
        with self.assertRaisesRegex(ValueError, "must contain text"):
            chunking.section_chunks(document)

    def test_command_displays_example_and_source_details(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = chunking.main([])
        self.assertEqual(result, 0)
        self.assertIn("Source: AUTH-1001-v1.json", output.getvalue())
        self.assertIn("Section: delegation", output.getvalue())
        self.assertIn("3 passages, 53 combined words, 10 repeated words", output.getvalue())
        self.assertIn("Complete section: 1 passage, 43 combined words", output.getvalue())

    def test_command_rejects_archived_documents_and_unknown_sections(self):
        for arguments, message in (
            (["--document-id", "SIM-1024-v1", "--section-id", "appointments"], "No approved, effective document"),
            (["--section-id", "not_a_section"], "was not found"),
        ):
            with self.subTest(arguments=arguments), redirect_stdout(io.StringIO()) as output:
                self.assertEqual(chunking.main(arguments), 1)
                self.assertIn(message, output.getvalue())

    def test_command_explains_invalid_configuration(self):
        settings = copy.deepcopy(load_settings())
        settings["chunking_experiment"]["overlap_words"] = 20
        with patch.object(chunking, "load_settings", return_value=settings), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(chunking.main([]), 1)
            self.assertIn("overlap_words", output.getvalue())
        del settings["chunking_experiment"]
        with patch.object(chunking, "load_settings", return_value=settings), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(chunking.main([]), 1)
            self.assertIn("settings.toml", output.getvalue())


if __name__ == "__main__":
    unittest.main()
