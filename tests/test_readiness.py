import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from retail_copilot import readiness


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)

    def write_env(self, text):
        (self.root / ".env").write_text(text, encoding="utf-8-sig")

    def test_missing_file_is_allowed(self):
        self.assertEqual(
            readiness.credential_presence(self.root, {}),
            {name: False for name in readiness.CONFIGURATION_NAMES},
        )

    def test_credential_reader_keeps_environment_precedence_and_returns_no_default_secret(self):
        self.write_env("OPENAI_API_KEY=fictional-file-value\n")
        self.assertEqual(readiness.read_credential("OPENAI_API_KEY", self.root, {}), "fictional-file-value")
        self.assertEqual(readiness.read_credential("OPENAI_API_KEY", self.root, {"OPENAI_API_KEY": ""}), "")
        self.assertEqual(readiness.read_credential("OPENAI_API_KEY", self.root, {"OPENAI_API_KEY": " fictional-process "}), "fictional-process")
        self.assertEqual(readiness.read_credential("PINECONE_API_KEY", self.root, {}), "")
        with self.assertRaises(ValueError):
            readiness.read_credential("UNKNOWN_KEY", self.root, {})

    def test_credential_reader_does_not_search_parent_or_modify_environment(self):
        self.write_env("OPENAI_API_KEY=fictional-parent\n")
        child = self.root / "separate-project"
        child.mkdir()
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(readiness.read_credential("OPENAI_API_KEY", child), "")
            self.assertEqual(readiness.read_credential("OPENAI_API_KEY", self.root), "fictional-parent")
            self.assertNotIn("OPENAI_API_KEY", os.environ)

    def test_blank_whitespace_and_unassigned_values_are_missing(self):
        self.write_env("OPENAI_API_KEY=\nPINECONE_API_KEY='   '\nPINECONE_INDEX_HOST\n")
        self.assertFalse(any(readiness.credential_presence(self.root, {}).values()))

    def test_file_values_support_quotes_comments_and_windows_utf8_bom(self):
        self.write_env(
            "# Fictional values for tests only\n"
            "OPENAI_API_KEY='fictional-openai'\n"
            'PINECONE_API_KEY="fictional-pinecone" # comment\n'
            "PINECONE_INDEX_HOST=https://example.invalid\n"
        )
        self.assertTrue(all(readiness.credential_presence(self.root, {}).values()))

    def test_environment_takes_priority_even_when_explicitly_empty(self):
        self.write_env("OPENAI_API_KEY=fictional-local\nPINECONE_API_KEY=\n")
        result = readiness.credential_presence(
            self.root, {"OPENAI_API_KEY": "", "PINECONE_API_KEY": "fictional-environment"}
        )
        self.assertFalse(result["OPENAI_API_KEY"])
        self.assertTrue(result["PINECONE_API_KEY"])

    def test_parent_project_env_is_not_used(self):
        self.write_env("OPENAI_API_KEY=fictional-parent\n")
        child = self.root / "separate-project"
        child.mkdir()
        self.assertFalse(any(readiness.credential_presence(child, {}).values()))

    def test_reading_file_does_not_change_process_environment(self):
        self.write_env("OPENAI_API_KEY=fictional-local\n")
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(readiness.credential_presence(self.root)["OPENAI_API_KEY"])
            self.assertNotIn("OPENAI_API_KEY", os.environ)

    def test_cli_never_prints_values_or_claims_verified_access(self):
        self.write_env("OPENAI_API_KEY=fictional-private-value\n")
        output = io.StringIO()
        with (
            patch.object(readiness, "PROJECT_ROOT", self.root),
            patch.dict(os.environ, {}, clear=True),
            redirect_stdout(output),
        ):
            self.assertEqual(readiness.main(), 0)
        self.assertIn("OPENAI_API_KEY: present (not verified)", output.getvalue())
        self.assertIn("PINECONE_API_KEY: missing", output.getvalue())
        self.assertNotIn("fictional-private-value", output.getvalue())

    def test_unreadable_file_reports_safe_message_without_raw_exception(self):
        output = io.StringIO()
        with (
            patch.object(Path, "open", side_effect=OSError("fictional-sensitive-detail")),
            redirect_stdout(output),
        ):
            self.assertEqual(readiness.main(), 1)
        self.assertIn("Check its permissions and UTF-8 encoding", output.getvalue())
        self.assertNotIn("fictional-sensitive-detail", output.getvalue())


if __name__ == "__main__":
    unittest.main()
