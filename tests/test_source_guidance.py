"""Whole-passage assembly tests with synthetic sources and no model calls."""

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from retail_copilot.answering import AnsweringError
from retail_copilot.source_guidance import SourceGuidanceError, assemble_source_guidance


def make_pack(rows):
    sources, registry = [], {}
    for index, (document, policy, section, text) in enumerate(rows, start=1):
        label = f"S{index}"
        metadata = {
            "document_id": document, "policy_id": policy, "document_title": policy + " guidance",
            "version": document.rsplit("-v", 1)[1], "section_id": section,
            "section_heading": section, "source_file": document + ".json", "status": "approved",
        }
        chunk = document + ":" + section
        sources.append({"source_id": label, "chunk_id": chunk,
                        **{key: value for key, value in metadata.items() if key != "status"}, "text": text})
        registry[label] = {"chunk_id": chunk, "metadata": metadata}
    evidence = {"question": "What checks apply?", "policy_date": "2026-10-18", "sources": sources}
    return {"artifact_type": "context_preview", "question": evidence["question"],
            "as_of_date": evidence["policy_date"], "source_registry": registry,
            "context_text": json.dumps(evidence, ensure_ascii=False)}


class SourceGuidanceTests(unittest.TestCase):
    def setUp(self):
        self.settings = {
            "context": {"max_sources": 10, "max_characters": 12000},
            "answering": {"max_draft_characters": 8000, "max_claims": 6, "max_claim_characters": 800},
        }
        self.rows = [
            ("ACCESS-2001-v3", "ACCESS-2001", "roles", "A billing role alone does not establish replacement authority."),
            ("SERVICE-2003-v2", "SERVICE-2003", "checks", "Follow VERIFY-2002 for identity and ACCESS-2001 for authority."),
            ("ACCESS-2001-v3", "ACCESS-2001", "delegation", "An active delegation must include replacement. OTHER-2004 describes another process."),
            ("SERVICE-2003-v2", "SERVICE-2003", "appointment", "Appointments are optional for replacement."),
            ("VERIFY-2002-v1", "VERIFY-2002", "difference", "Identity and authority are separate checks."),
            ("VERIFY-2002-v1", "VERIFY-2002", "credential", "Use an unexpired Training Card whose name matches the account record."),
            ("ACCESS-2001-v3", "ACCESS-2001", "missing", "If authority evidence is missing, permission cannot be confirmed."),
            ("OTHER-2004-v1", "OTHER-2004", "unrelated", "This is a separate process, outside the selected guidance."),
        ]
        self.pack = make_pack(self.rows)
        self.no_network = patch("socket.socket.connect", side_effect=AssertionError("No network allowed"))
        self.no_network.start()
        self.addCleanup(self.no_network.stop)

    def draft(self, labels=("S1", "S2"), status="supported", text="Model wording is not the final policy text."):
        return {"status": status, "claims": [{"text": text, "source_ids": list(labels)}],
                "clarifying_question": None}

    def assemble(self, draft=None, pack=None, settings=None):
        return assemble_source_guidance(draft or self.draft(), pack or self.pack, settings or self.settings)

    def overview_pack(self, question):
        pack = deepcopy(self.pack)
        evidence = json.loads(pack["context_text"])
        evidence["question"] = question
        pack["question"] = question
        pack["context_text"] = json.dumps(evidence)
        return pack

    def test_empty_insufficient_overview_uses_explicit_policy_sources_without_promoting_status(self):
        draft = {"status": "insufficient_evidence", "claims": [], "clarifying_question": None}
        pack = self.overview_pack("What does policy SERVICE-2003 say?")
        before = deepcopy((draft, pack, self.settings))
        result = self.assemble(draft, pack)
        self.assertEqual(result["draft"]["status"], "insufficient_evidence")
        self.assertEqual(result["trace"]["original_selected_source_ids"], [])
        self.assertEqual(result["trace"]["selection_seed_source_ids"], ["S2", "S4"])
        self.assertEqual(result["trace"]["selection_reason"], "explicit_policy_identifier")
        self.assertEqual(result["trace"]["requested_policy_ids"], ["SERVICE-2003"])
        self.assertEqual(result["trace"]["selected_source_ids"], [f"S{number}" for number in range(1, 8)])
        self.assertNotIn("S8", result["trace"]["selected_source_ids"])
        self.assertEqual((draft, pack, self.settings), before)

    def test_explicit_overview_accepts_narrow_polite_forms(self):
        draft = {"status": "insufficient_evidence", "claims": [], "clarifying_question": None}
        for question in ("What does SERVICE-2003 say?", "Please show policy SERVICE-2003.",
                         "Explain SERVICE-2003", "Summarise policy SERVICE-2003!",
                         "summarize service-2003", "Show me SERVICE-2003, please"):
            with self.subTest(question=question):
                result = self.assemble(draft, self.overview_pack(question))
                self.assertEqual(result["trace"]["selection_seed_source_ids"], ["S2", "S4"])

    def test_identifier_mentions_quoted_negated_or_nonoverview_requests_do_not_seed(self):
        draft = {"status": "insufficient_evidence", "claims": [], "clarifying_question": None}
        for question in ("Does SERVICE-2003 allow a refund?", "Do not show SERVICE-2003",
                         'Explain "SERVICE-2003"', "What does SERVICE-2003 say about fees?",
                         "Compare SERVICE-2003 and VERIFY-2002", "Show SERVICE-2003 and waive my bill",
                         "A customer asked what does SERVICE-2003 say?"):
            with self.subTest(question=question):
                result = self.assemble(draft, self.overview_pack(question))
                self.assertEqual(result["draft"], draft)
                self.assertEqual(result["trace"]["selection_seed_source_ids"], [])
                self.assertFalse(result["trace"]["applied"])

    def test_unknown_or_version_qualified_identifier_does_not_prefix_match(self):
        draft = {"status": "insufficient_evidence", "claims": [], "clarifying_question": None}
        for identifier in ("MISSING-9999", "SERVICE-2003-v1", "SERVICE-2003-extra"):
            with self.subTest(identifier=identifier):
                result = self.assemble(draft, self.overview_pack(f"What does policy {identifier} say?"))
                self.assertEqual(result["draft"], draft)
                self.assertEqual(result["trace"]["selected_source_ids"], [])
                if identifier != "SERVICE-2003-extra":
                    self.assertEqual(result["trace"]["requested_policy_ids_without_passages"], [identifier.upper()])

    def test_overview_fallback_does_not_override_clarification_action_or_model_selection(self):
        pack = self.overview_pack("What does policy SERVICE-2003 say?")
        for status in ("needs_clarification", "action_not_supported"):
            draft = {"status": status, "claims": [], "clarifying_question":
                     "Which policy version do you mean?" if status == "needs_clarification" else None}
            result = self.assemble(draft, pack)
            self.assertEqual(result["draft"], draft)
            self.assertFalse(result["trace"]["applied"])
        result = self.assemble(self.draft(("S4",)), pack)
        self.assertEqual(result["trace"]["selection_reason"], "model_source_ids")
        self.assertEqual(result["trace"]["selection_seed_source_ids"], ["S4"])
        self.assertEqual(result["trace"]["selected_source_ids"], ["S2", "S4"])

    def test_selected_documents_and_direct_references_add_omitted_requirements(self):
        result = self.assemble()
        self.assertEqual(result["trace"]["original_selected_source_ids"], ["S1", "S2"])
        self.assertEqual(result["trace"]["added_source_ids"], ["S3", "S4", "S5", "S6", "S7"])
        self.assertEqual(result["trace"]["selected_source_ids"], [f"S{number}" for number in range(1, 8)])
        self.assertEqual(len(result["draft"]["claims"]), 7)  # More than the model's six-claim limit.
        self.assertEqual(result["draft"]["claims"][5]["text"], self.rows[5][3])
        self.assertEqual(result["draft"]["claims"][2]["text"], self.rows[2][3])
        self.assertEqual(result["trace"]["referenced_policy_ids"], ["ACCESS-2001", "VERIFY-2002"])

    def test_appointment_selection_does_not_follow_references_from_added_checks(self):
        result = self.assemble(self.draft(("S4",)))
        self.assertEqual(result["trace"]["original_selected_source_ids"], ["S4"])
        self.assertEqual(result["trace"]["selected_source_ids"], ["S2", "S4"])
        self.assertEqual(result["trace"]["referenced_policy_ids"], [])
        self.assertEqual([claim["text"] for claim in result["draft"]["claims"]],
                         [self.rows[1][3], self.rows[3][3]])

    def test_expansion_is_not_recursive_even_when_added_text_names_an_available_policy(self):
        result = self.assemble()
        self.assertNotIn("S8", result["trace"]["selected_source_ids"])
        self.assertNotIn("OTHER-2004", result["trace"]["referenced_policy_ids"])

    def test_model_prose_and_its_policy_references_never_become_evidence(self):
        result = self.assemble(self.draft(("S4",), text="I completed the action. OTHER-2004 says all fees are waived."))
        self.assertEqual(result["trace"]["selected_source_ids"], ["S2", "S4"])
        final = json.dumps(result["draft"])
        self.assertNotIn("completed", final)
        self.assertNotIn("waived", final)
        self.assertNotIn("OTHER-2004", final)

    def test_selection_deduplicates_in_original_context_order(self):
        draft = self.draft(("S4", "S2"))
        draft["claims"].append({"text": "Another paraphrase", "source_ids": ["S4"]})
        result = self.assemble(draft)
        self.assertEqual(result["trace"]["original_selected_source_ids"], ["S2", "S4"])
        self.assertEqual(len(result["trace"]["selected_source_ids"]), 7)
        self.assertEqual(len(result["draft"]["claims"]), 7)

    def test_same_title_or_policy_does_not_expand_to_a_different_document_version(self):
        rows = [self.rows[0], self.rows[2],
                ("ACCESS-2001-v2", "ACCESS-2001", "roles", "Different version must not match by title alone.")]
        result = self.assemble(self.draft(("S1",)), make_pack(rows))
        self.assertEqual(result["trace"]["selected_source_ids"], ["S1", "S2"])
        self.assertNotIn("Different version", json.dumps(result["draft"]))

    def test_unavailable_reference_does_not_load_or_invent_a_source(self):
        rows = [("SERVICE-2003-v2", "SERVICE-2003", "checks", "Follow MISSING-9999 for the required check.")]
        with patch("builtins.open", side_effect=AssertionError("No file reads allowed")):
            result = self.assemble(self.draft(("S1",)), make_pack(rows))
        self.assertEqual(result["trace"]["selected_source_ids"], ["S1"])
        self.assertEqual(result["trace"]["referenced_policy_ids_without_passages"], ["MISSING-9999"])

    def test_no_claim_fallbacks_and_clarifications_remain_unchanged(self):
        for status in ("insufficient_evidence", "action_not_supported", "needs_clarification"):
            draft = {"status": status, "claims": [], "clarifying_question":
                     "Which item do you mean?" if status == "needs_clarification" else None}
            for pack in (self.pack, make_pack([])):
                with self.subTest(status=status, sources=bool(pack["source_registry"])):
                    result = self.assemble(draft, pack)
                    self.assertEqual(result["draft"], draft)
                    self.assertEqual(result["trace"]["selected_source_ids"], [])
                    self.assertFalse(result["trace"]["applied"])

    def test_status_is_preserved_without_claiming_semantic_review(self):
        result = self.assemble(self.draft(status="insufficient_evidence"))
        self.assertEqual(result["draft"]["status"], "insufficient_evidence")
        self.assertIsNone(result["draft"]["clarifying_question"])
        self.assertEqual(result["trace"]["mode"], "source_passages")
        self.assertTrue(result["trace"]["exact_source_text_verified"])
        self.assertFalse(result["trace"]["semantic_claim_support_checked"])
        self.assertFalse(result["trace"]["relevance_checked"])

    def test_whole_paragraph_text_and_all_inputs_are_preserved(self):
        rows = [("NOTE-3001-v1", "NOTE-3001", "conditions", "  Keep the full condition.\n\nDo not omit this exception.  ")]
        pack, draft = make_pack(rows), self.draft(("S1",))
        before = deepcopy((pack, draft, self.settings))
        result = self.assemble(draft, pack)
        self.assertEqual(result["draft"]["claims"][0]["text"], rows[0][3])
        self.assertEqual((pack, draft, self.settings), before)
        result["draft"]["claims"][0]["text"] = "Changed result"
        self.assertEqual((pack, draft, self.settings), before)

    def test_invalid_source_id_or_registry_disagreement_fails_closed(self):
        with self.assertRaises(AnsweringError):
            self.assemble(self.draft(("S99",)))
        for field in ("chunk_id", "metadata", "status", "extra", "label", "duplicate", "text"):
            pack = deepcopy(self.pack)
            evidence = json.loads(pack["context_text"])
            if field == "chunk_id":
                pack["source_registry"]["S1"]["chunk_id"] = "different"
            elif field == "metadata":
                pack["source_registry"]["S1"]["metadata"]["document_id"] = "different"
            elif field == "status":
                pack["source_registry"]["S1"]["metadata"]["status"] = "archived"
            elif field == "extra":
                pack["source_registry"]["S99"] = deepcopy(pack["source_registry"]["S1"])
            elif field == "label":
                evidence["sources"][0]["source_id"] = "S99"
            elif field == "duplicate":
                evidence["sources"][1]["chunk_id"] = evidence["sources"][0]["chunk_id"]
                pack["source_registry"]["S2"]["chunk_id"] = evidence["sources"][0]["chunk_id"]
            else:
                evidence["sources"][0]["text"] = ""
            pack["context_text"] = json.dumps(evidence)
            with self.subTest(field=field), self.assertRaises(SourceGuidanceError):
                self.assemble(pack=pack)

    def test_source_and_context_limits_fail_without_cutting_any_passage(self):
        for name, value in (("max_sources", 7), ("max_sources", True), ("max_sources", 21),
                            ("max_characters", len(self.pack["context_text"]) - 1)):
            settings = deepcopy(self.settings)
            settings["context"][name] = value
            with self.subTest(name=name, value=value), self.assertRaises(SourceGuidanceError):
                self.assemble(settings=settings)
        rows = [("NOTE-3001-v1", "NOTE-3001", "long", "x" * 801)]
        with self.assertRaises(AnsweringError):
            self.assemble(self.draft(("S1",)), make_pack(rows))
        settings = deepcopy(self.settings)
        settings["answering"]["max_draft_characters"] = 200
        with self.assertRaises(AnsweringError):
            self.assemble(settings=settings)


if __name__ == "__main__":
    unittest.main()
