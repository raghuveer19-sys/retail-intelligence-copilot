"""Hand-written draft tests; passing these does not measure a language model."""

from contextlib import redirect_stdout
from copy import deepcopy
from datetime import date
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from retail_copilot import answering
from retail_copilot.context import ContextError, build_context
from retail_copilot.documents import PROJECT_ROOT, approved_documents, load_documents, load_settings
from retail_copilot.chunking import section_chunks
from retail_copilot.pinecone_records import to_pinecone_record


IDS = ("SIM-1024-v2:appointments:section-v1", "SIM-1024-v2:checks:section-v1",
       "AUTH-1001-v1:roles:section-v1", "IDV-1001-v1:training_id:section-v1")


class AnsweringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = load_settings()
        cls.instructions = (PROJECT_ROOT / "prompts/answering.md").read_text(encoding="utf-8")
        policies = approved_documents(load_documents(PROJECT_ROOT / "data/knowledge"), date(2026, 10, 15))
        records = {}
        for policy in policies:
            for chunk in section_chunks(policy):
                mapped = to_pinecone_record({
                    "provider": "ollama", "model": cls.settings["embedding"]["model"], "dimensions": 768,
                    "chunk_id": chunk.id, "text": chunk.page_content, "metadata": deepcopy(chunk.metadata), "vector": [0.1] * 768,
                }, cls.settings["embedding"])
                records[chunk.id] = {"_id": chunk.id, "embedding": mapped["values"], **mapped["metadata"]}
        cls.prepared = {"documents": list(records.values()), "as_of_date": "2026-10-15",
                        "model_digest": "a" * 64, "corpus_sha256": "b" * 64}
        hits = []
        for identifier in IDS:
            fields = deepcopy(records[identifier])
            fields.pop("_id")
            fields.pop("embedding")
            text = fields.pop("text")
            hits.append({"chunk_id": identifier, "text": text, "metadata": fields, "score": 0.5})
        cls.result = {"schema_version": 1, "question": "What checks apply to a fictional SIM replacement?",
                      "as_of_date": "2026-10-15", "model": cls.settings["embedding"]["model"], "dimensions": 768,
                      "model_digest": "a" * 64, "corpus_sha256": "b" * 64,
                      "index_name": cls.settings["retrieval"]["index_name"], "namespace": cls.settings["retrieval"]["namespace"], "matches": hits}
        cls.pack = build_context(cls.result, cls.prepared, cls.settings)

    def draft(self, **changes):
        return {"status": "supported", "claims": [{"text": "Use an unexpired Fictional Training ID card matching the fictional account name.", "source_ids": ["S4"]}],
                "clarifying_question": None, **changes}

    def render(self, draft):
        return answering.render_draft(json.dumps(draft), self.pack, self.settings)

    def test_prompt_separates_instructions_from_unchanged_evidence(self):
        preview = answering.build_prompt(self.pack, self.instructions, self.settings)
        self.assertEqual([message["role"] for message in preview["messages"]], ["system", "user"])
        supplied = json.loads(preview["messages"][1]["content"])
        self.assertEqual(supplied["question"], self.pack["question"])
        self.assertEqual([source["text"] for source in supplied["sources"]],
                         [source["text"] for source in json.loads(self.pack["context_text"])["sources"]])
        self.assertNotIn(self.pack["question"], preview["messages"][0]["content"])
        self.assertEqual(preview["response_format"]["allowed_source_ids"], ["S1", "S2", "S3", "S4"])
        self.assertEqual(preview["message_characters"], sum(len(message["content"]) for message in preview["messages"]))
        self.assertFalse(preview["model_call_made"])
        self.assertFalse(preview["answer_generated"])
        self.assertIsNone(preview["model_input_tokens"])

    def test_revalidation_accepts_original_pack_without_mutating_it(self):
        before = deepcopy(self.pack)
        checked = answering.revalidate_pack(self.pack, self.prepared, self.settings)
        self.assertEqual(checked, self.pack)
        self.assertEqual(before, self.pack)

    def test_changed_text_title_registry_label_or_model_is_rejected(self):
        for change in ("text", "title", "registry", "label", "extra_label", "model", "question", "artifact", "notices"):
            pack = deepcopy(self.pack)
            evidence = json.loads(pack["context_text"])
            if change in ("text", "title", "label"):
                evidence["sources"][0][{"text": "text", "title": "document_title", "label": "source_id"}[change]] = "changed"
                pack["context_text"] = json.dumps(evidence, ensure_ascii=False, indent=2)
            elif change == "registry":
                pack["source_registry"]["S1"]["chunk_id"] = IDS[1]
            elif change == "extra_label":
                pack["source_registry"]["S99"] = deepcopy(pack["source_registry"]["S1"])
            else:
                pack[{"model": "model_digest", "question": "question", "artifact": "artifact_type", "notices": "references_without_passages"}[change]] = "changed"
            with self.subTest(change=change), self.assertRaises((answering.AnsweringError, ContextError)):
                answering.revalidate_pack(pack, self.prepared, self.settings)

    def test_empty_context_uses_fixed_fallback_without_model_messages(self):
        pack = build_context({**self.result, "matches": []}, self.prepared, self.settings)
        checked = answering.revalidate_pack(pack, self.prepared, self.settings)
        preview = answering.build_prompt(checked, self.instructions, self.settings)
        self.assertEqual(preview["messages"], [])
        response = answering.render_draft(json.dumps(preview["empty_context_fallback"]), checked, self.settings)
        self.assertEqual(response["status"], "insufficient_evidence")
        self.assertEqual(response["citations"], [])
        with self.assertRaises(answering.AnsweringError):
            answering.validate_draft(json.dumps(self.draft()), checked, self.settings)

    def test_citation_details_come_from_the_retrieved_registry(self):
        response = self.render(self.draft())
        citation = response["citations"][0]
        self.assertEqual(citation["chunk_id"], IDS[3])
        self.assertEqual(citation["source_file"], "IDV-1001-v1.json")
        self.assertEqual(citation["section_heading"], "Training identification")
        self.assertIn("[S4]", response["text"])
        self.assertNotIn("[S1]", response["text"])
        self.assertTrue(response["source_ids_valid"])
        self.assertFalse(response["claim_support_checked"])

    def test_multiple_claims_share_one_source_entry(self):
        draft = self.draft()
        draft["claims"].append({"text": "Identity and account-authority checks are required.", "source_ids": ["S2", "S4"]})
        response = self.render(draft)
        self.assertEqual([citation["source_id"] for citation in response["citations"]], ["S4", "S2"])

    def test_unknown_duplicate_or_unstructured_source_ids_reject_whole_draft(self):
        for ids in (["S99"], ["S4", "S4"], [], "S4", [4], ["[S4]"]):
            draft = self.draft()
            draft["claims"].append({"text": "Another claim", "source_ids": ids})
            with self.subTest(ids=ids), self.assertRaises(answering.AnsweringError):
                self.render(draft)

    def test_inline_citations_and_urls_are_not_accepted_as_model_bibliography(self):
        for text in ("A claim [S99]", "A claim https://invented.example/policy", "A claim WWW.example.test"):
            draft = self.draft(claims=[{"text": text, "source_ids": ["S4"]}])
            with self.assertRaises(answering.AnsweringError):
                self.render(draft)

    def test_extra_fields_including_reasoning_or_invented_source_names_rejected(self):
        for draft in (self.draft(reasoning="Do not expose reasoning"), self.draft(claims=[{"text": "Claim", "source_ids": ["S4"], "source_file": "invented.json"}])):
            with self.assertRaises(answering.AnsweringError):
                self.render(draft)

    def test_invalid_json_duplicate_fields_and_markdown_fences_rejected(self):
        valid = json.dumps(self.draft())
        for raw in ("", "not json", "```json\n" + valid + "\n```", valid + " trailing text", "[]", "null",
                    '{"status":"supported","status":"insufficient_evidence","claims":[],"clarifying_question":null}'):
            with self.subTest(raw=raw[:20]), self.assertRaises(answering.AnsweringError):
                answering.validate_draft(raw, self.pack, self.settings)

    def test_status_and_clarification_rules(self):
        for draft in (self.draft(status="complete"), self.draft(status=[]), self.draft(claims=[]),
                      self.draft(clarifying_question="Which SIM?"), self.draft(status="needs_clarification"),
                      self.draft(status="needs_clarification", claims=[], clarifying_question=" ")):
            with self.assertRaises(answering.AnsweringError):
                self.render(draft)
        response = self.render(self.draft(status="needs_clarification", claims=[], clarifying_question="Is this a physical SIM or an eSIM?"))
        self.assertIn("physical SIM", response["text"])
        self.assertEqual(response["citations"], [])

    def test_insufficient_and_action_statuses_render_fixed_limitations(self):
        for status in ("insufficient_evidence", "action_not_supported"):
            response = self.render(self.draft(status=status, claims=[]))
            self.assertIn(answering.STATUS_MESSAGES[status], response["text"])
            self.assertEqual(response["citations"], [])
        response = self.render(self.draft(status="insufficient_evidence"))
        self.assertEqual(len(response["citations"]), 1)

    def test_valid_source_does_not_establish_semantic_support_or_action_truth(self):
        # These deliberately wrong statements pass ID checks, exposing the boundary.
        for text in ("Identity verification is unnecessary.", "I replaced your SIM."):
            response = self.render(self.draft(claims=[{"text": text, "source_ids": ["S1"]}]))
            self.assertTrue(response["source_ids_valid"])
            self.assertFalse(response["claim_support_checked"])
            self.assertFalse(response["action_claims_checked"])

    def test_limits_reject_oversized_drafts_claims_and_excess_claims(self):
        draft = self.draft()
        raw = json.dumps(draft)
        settings = deepcopy(self.settings)
        settings["answering"]["max_draft_characters"] = len(raw)
        answering.validate_draft(raw, self.pack, settings)
        settings["answering"]["max_draft_characters"] -= 1
        with self.assertRaises(answering.AnsweringError):
            answering.validate_draft(raw, self.pack, settings)
        for bad in (self.draft(claims=draft["claims"] * 7), self.draft(claims=[{"text": "x" * 801, "source_ids": ["S4"]}]),
                    self.draft(claims=[{"text": " ", "source_ids": ["S4"]}]), self.draft(claims=None)):
            with self.assertRaises(answering.AnsweringError):
                self.render(bad)

    def test_empty_instructions_and_invalid_limits_rejected(self):
        with self.assertRaises(answering.AnsweringError):
            answering.build_prompt(self.pack, " ", self.settings)
        for key, value in (("max_claims", True), ("max_claims", 21), ("max_draft_characters", 0), ("max_claim_characters", 4001)):
            settings = deepcopy(self.settings)
            settings["answering"][key] = value
            with self.assertRaises(answering.AnsweringError):
                answering.build_prompt(self.pack, self.instructions, settings)

    def run_cli(self, root, settings, output):
        with patch.object(answering, "PROJECT_ROOT", root), patch.object(answering, "load_settings", return_value=settings), patch.object(
            answering, "prepare_upload", return_value=self.prepared,
        ), patch("socket.socket.connect", side_effect=AssertionError("No network allowed")), redirect_stdout(output):
            return answering.main([])

    def write_inputs(self, root):
        context_path = root / self.settings["answering"]["input_file"]
        context_path.parent.mkdir(parents=True, exist_ok=True)
        context_path.write_text(json.dumps(self.pack), encoding="utf-8")
        prompt = root / self.settings["answering"]["system_prompt_file"]
        prompt.parent.mkdir(parents=True, exist_ok=True)
        prompt.write_text(self.instructions, encoding="utf-8")
        return context_path

    def test_cli_preview_makes_no_requests_and_preserves_input(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            input_path = self.write_inputs(root)
            before = input_path.read_bytes()
            output = io.StringIO()
            self.assertEqual(self.run_cli(root, self.settings, output), 0)
            preview = json.loads((root / self.settings["answering"]["output_file"]).read_text(encoding="utf-8"))
            self.assertEqual(preview["service_calls_made"], 0)
            self.assertEqual(input_path.read_bytes(), before)
            self.assertIn("OFFLINE PREVIEW", output.getvalue())
            self.assertEqual(self.run_cli(root, self.settings, io.StringIO()), 0)

    def test_cli_output_cannot_replace_prior_artifacts_or_escape_generated_folder(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            input_path = self.write_inputs(root)
            for name in (self.settings["answering"]["input_file"], "README.md", "data/processed/another-report.json"):
                settings = deepcopy(self.settings)
                settings["answering"]["output_file"] = name
                path = root / name
                if path != input_path:
                    path.write_text('{"artifact_type": "other"}', encoding="utf-8")
                before = path.read_bytes()
                self.assertEqual(self.run_cli(root, settings, io.StringIO()), 1)
                self.assertEqual(path.read_bytes(), before)

    def test_cli_rejects_prompt_outside_prompts_and_keeps_last_preview_on_failure(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            input_path = self.write_inputs(root)
            self.assertEqual(self.run_cli(root, self.settings, io.StringIO()), 0)
            path = root / self.settings["answering"]["output_file"]
            before = path.read_bytes()
            settings = deepcopy(self.settings)
            settings["answering"]["system_prompt_file"] = ".env"
            self.assertEqual(self.run_cli(root, settings, io.StringIO()), 1)
            self.assertEqual(path.read_bytes(), before)
            input_path.write_text("private malformed input", encoding="utf-8")
            output = io.StringIO()
            self.assertEqual(self.run_cli(root, self.settings, output), 1)
            self.assertNotIn("private malformed input", output.getvalue())
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
