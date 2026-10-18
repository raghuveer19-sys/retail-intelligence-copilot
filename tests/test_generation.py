"""Mocked local-generation checks; these do not measure real model answer quality."""

from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import test_answering as answering_fixtures
from retail_copilot import generate
from retail_copilot.answering import AnsweringError
from retail_copilot.context import build_context


class GenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse the evidence fixture without inheriting or rediscovering its tests.
        fixture = answering_fixtures.AnsweringTests
        fixture.setUpClass()
        for name in ("settings", "instructions", "prepared", "result", "pack"):
            setattr(cls, name, deepcopy(getattr(fixture, name)))

    def draft(self):
        return {"status": "supported", "claims": [{
            "text": "Use an unexpired Fictional Training ID card matching the fictional account name.",
            "source_ids": ["S4"],
        }], "clarifying_question": None}

    def response(self):
        return {"model": self.settings["generation"]["model"], "done": True, "done_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(self.draft()),
                            "thinking": "PRIVATE_THINKING_SENTINEL"},
                "prompt_eval_count": 1900, "eval_count": 100, "total_duration": 2_000_000_000,
                "unrelated_provider_details": "PRIVATE_PROVIDER_SENTINEL"}

    def model_details(self):
        return {"digest": "d" * 64, "maximum_context_tokens": 262144,
                "think": True, "tokenizer": "gpt2", "template_sha256": "e" * 64}

    def shown_model(self):
        return {"capabilities": ["completion", "thinking"], "template": "x" * 1506,
                "thinking": {"values": [True]},
                "model_info": {"general.architecture": "qwen3", "qwen3.context_length": 262144,
                               "tokenizer.ggml.model": "gpt2"}}

    def generate_mocked(self, response):
        with patch.object(generate, "inspect_model", return_value=self.model_details()), patch.object(
            generate, "request_local_json", return_value=response,
        ):
            return generate.generate_answer(self.pack, self.instructions, self.settings)

    def test_success_persists_only_final_fields_and_keeps_semantic_review_pending(self):
        before = deepcopy(self.pack)
        output = io.StringIO()
        with redirect_stdout(output):
            result = self.generate_mocked(self.response())
        self.assertTrue(result["model_call_made"])
        self.assertTrue(result["answer_generated"])
        self.assertEqual(result["model_digest"], "d" * 64)
        self.assertEqual(result["usage"]["prompt_tokens"], 1900)
        self.assertEqual(result["usage"]["generated_tokens_including_thinking"], 100)
        self.assertEqual(result["provider_duration_seconds"], 2)
        self.assertEqual(result["external_request_charge_usd"], "0")
        self.assertEqual(result["claim_review_status"], "pending")
        self.assertTrue(result["answer"]["source_ids_valid"])
        self.assertFalse(result["answer"]["claim_support_checked"])
        self.assertFalse(result["answer"]["action_claims_checked"])
        self.assertEqual(result["answer"]["citations"][0]["source_file"], "IDV-1001-v1.json")
        self.assertNotIn("PRIVATE_THINKING_SENTINEL", json.dumps(result) + output.getvalue())
        self.assertNotIn("PRIVATE_PROVIDER_SENTINEL", json.dumps(result) + output.getvalue())
        self.assertEqual(self.pack, before)

    def test_request_uses_schema_and_final_nonstreaming_local_options_without_tools(self):
        with patch.object(generate, "inspect_model", return_value=self.model_details()), patch.object(
            generate, "request_local_json", return_value=self.response(),
        ) as request:
            generate.generate_answer(self.pack, self.instructions, self.settings)
        options, route, payload = request.call_args.args
        self.assertEqual(route, "/api/chat")
        self.assertEqual(options["api_base_url"], "http://127.0.0.1:11434")
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["keep_alive"], "0s")
        self.assertTrue(payload["think"])
        self.assertNotIn("tools", payload)
        self.assertEqual(json.loads(payload["messages"][1]["content"])["question"], self.pack["question"])
        allowed = payload["format"]["properties"]["claims"]["items"]["properties"]["source_ids"]["items"]["enum"]
        self.assertEqual(allowed, ["S1", "S2", "S3", "S4"])
        self.assertFalse(payload["format"]["additionalProperties"])

    def test_empty_context_bypasses_all_model_requests(self):
        pack = build_context({**self.result, "matches": []}, self.prepared, self.settings)
        with patch.object(generate, "inspect_model", side_effect=AssertionError("No model inspection")), patch.object(
            generate, "request_local_json", side_effect=AssertionError("No HTTP call"),
        ):
            result = generate.generate_answer(pack, self.instructions, self.settings)
        self.assertFalse(result["model_call_made"])
        self.assertFalse(result["answer_generated"])
        self.assertEqual(result["answer"]["status"], "insufficient_evidence")
        self.assertEqual(result["answer"]["citations"], [])
        self.assertEqual(result["claim_review_status"], "no_model_claims")
        self.assertIsNone(result["usage"])

    def test_warm_batch_keeps_model_for_requested_seconds_and_records_it(self):
        with patch.object(generate, "inspect_model", return_value=self.model_details()), patch.object(
            generate, "request_local_json", return_value=self.response(),
        ) as request:
            result = generate.generate_answer(self.pack, self.instructions, self.settings, keep_alive_seconds=300)
        self.assertEqual(request.call_args.args[2]["keep_alive"], "300s")
        self.assertEqual(result["keep_alive_seconds"], 300)
        self.assertTrue(result["answer_generated"])

    def test_invalid_keep_alive_stops_before_model_or_http_calls(self):
        for seconds in (True, False, -1, 601, 300.0, "300"):
            with self.subTest(seconds=seconds), patch.object(generate, "inspect_model", side_effect=AssertionError("No model inspection")), patch.object(
                generate, "request_local_json", side_effect=AssertionError("No HTTP call"),
            ), self.assertRaises(generate.GenerationError):
                generate.generate_answer(self.pack, self.instructions, self.settings, keep_alive_seconds=seconds)

    def test_unknown_source_and_invalid_drafts_are_rejected(self):
        unknown = self.draft()
        unknown["claims"][0]["source_ids"] = ["S99"]
        reasoning = {**self.draft(), "reasoning": "PRIVATE_THINKING_SENTINEL"}
        for content in (None, "", "not json", "```json\n{}\n```", json.dumps(unknown), json.dumps(reasoning)):
            response = self.response()
            response["message"]["content"] = content
            with self.subTest(content=content), self.assertRaises(AnsweringError):
                self.generate_mocked(response)

    def test_valid_source_does_not_certify_claim_truth(self):
        response = self.response()
        draft = self.draft()
        draft["claims"] = [{"text": "I have replaced your SIM.", "source_ids": ["S1"]}]
        response["message"]["content"] = json.dumps(draft)
        result = self.generate_mocked(response)
        self.assertFalse(result["answer"]["claim_support_checked"])
        self.assertFalse(result["answer"]["action_claims_checked"])
        self.assertEqual(result["claim_review_status"], "pending")

    def test_incomplete_wrong_model_or_tool_response_is_rejected(self):
        for change in ({"done": False}, {"done": 1}, {"done_reason": "length"}, {"model": "other"},
                       {"message": None}, {"message": {"role": "tool", "content": "{}"}},
                       {"message": {"role": "assistant", "content": "{}", "tool_calls": [{"name": "action"}]}}):
            with self.subTest(change=change), self.assertRaises(generate.GenerationError):
                self.generate_mocked({**self.response(), **change})

    def test_missing_invalid_or_limit_reaching_usage_is_rejected(self):
        for key, value in (("prompt_eval_count", 0), ("prompt_eval_count", True), ("prompt_eval_count", 100000),
                           ("eval_count", None), ("eval_count", 0),
                           ("eval_count", self.settings["generation"]["num_predict"]),
                           ("total_duration", -1), ("total_duration", 1.5), ("total_duration", True)):
            with self.subTest(key=key, value=value), self.assertRaises(generate.GenerationError):
                self.generate_mocked({**self.response(), key: value})

    def test_byte_budget_preserves_unicode_and_allows_exact_boundary(self):
        options = deepcopy(self.settings["generation"])
        messages = [{"role": "user", "content": "caf\u00e9"}]
        options["num_ctx"] = 5 + options["template_reserve_tokens"] + options["num_predict"]
        budget = generate.input_budget(messages, options)
        self.assertEqual(budget["message_utf8_bytes"], 5)
        self.assertIsNone(budget["exact_input_tokens"])
        options["num_ctx"] -= 1
        with self.assertRaises(generate.GenerationError):
            generate.input_budget(messages, options)

    def test_oversized_prompt_stops_before_model_inspection(self):
        settings = deepcopy(self.settings)
        settings["generation"]["num_ctx"] = 4096
        with patch.object(generate, "inspect_model", side_effect=AssertionError("No calls")), self.assertRaises(generate.GenerationError):
            generate.generate_answer(self.pack, self.instructions, settings)

    def test_invalid_or_cloud_generation_options_are_rejected(self):
        for key, value in (("provider", "openai"), ("model", "qwen3:cloud"), ("model", " "),
                           ("num_ctx", True), ("num_ctx", 65537), ("num_predict", 127),
                           ("template_reserve_tokens", 255), ("temperature", float("nan")), ("temperature", True),
                           ("thinking_when_metadata_missing", None), ("thinking_when_metadata_missing", 0),
                           ("thinking_when_metadata_missing", 1), ("thinking_when_metadata_missing", "false"),
                           ("thinking_when_metadata_missing", [])):
            settings = deepcopy(self.settings)
            settings["generation"][key] = value
            with self.subTest(key=key), self.assertRaises(generate.GenerationError):
                generate.generation_options(settings)

    def test_model_inspection_checks_local_completion_and_thinking_capabilities(self):
        for values, expected in (([True], True), ([False, True], False)):
            shown = self.shown_model()
            shown["thinking"]["values"] = values
            with patch.object(generate, "installed_model_digest", return_value="d" * 64), patch.object(
                generate, "request_local_json", return_value=shown,
            ) as request:
                details = generate.inspect_model(self.settings["generation"])
            self.assertIs(details["think"], expected)
            self.assertEqual(details["digest"], "d" * 64)
            self.assertEqual(request.call_args.args[1], "/api/show")

    def test_non_thinking_model_accepts_absent_or_null_thinking_and_requests_false(self):
        for missing in (False, True):
            shown = self.shown_model()
            shown["capabilities"] = ["completion", "tools"]
            shown["thinking"] = None
            response = self.response()
            response["message"].pop("thinking")
            settings = deepcopy(self.settings)
            settings["generation"].pop("thinking_when_metadata_missing", None)
            if missing:
                shown.pop("thinking")
            with self.subTest(missing=missing), patch.object(generate, "installed_model_digest", return_value="d" * 64), patch.object(
                generate, "request_local_json", side_effect=[shown, response],
            ) as request:
                result = generate.generate_answer(self.pack, self.instructions, settings)
            self.assertFalse(result["model_details"]["think"])
            self.assertIs(request.call_args.args[2]["think"], False)
            self.assertEqual(request.call_args.args[1], "/api/chat")

    def test_explicit_reviewed_fallback_controls_model_when_thinking_metadata_missing(self):
        for reviewed in (False, True):
            settings = deepcopy(self.settings)
            settings["generation"]["thinking_when_metadata_missing"] = reviewed
            shown = self.shown_model()
            shown["thinking"] = None
            response = self.response()
            if reviewed is False:
                response["message"].pop("thinking")
            with self.subTest(reviewed=reviewed), patch.object(generate, "installed_model_digest", return_value="d" * 64), patch.object(
                generate, "request_local_json", side_effect=[shown, response],
            ) as request:
                result = generate.generate_answer(self.pack, self.instructions, settings)
            self.assertIs(request.call_args.args[2]["think"], reviewed)
            self.assertIs(result["model_details"]["think"], reviewed)
            self.assertEqual(result["model_details"]["thinking_control_source"], "reviewed_configuration_or_non_thinking_capability")

    def test_unexpected_thinking_is_rejected_when_requested_disabled_without_leakage(self):
        details = {**self.model_details(), "think": False}
        with patch.object(generate, "inspect_model", return_value=details), patch.object(
            generate, "request_local_json", return_value=self.response(),
        ), self.assertRaises(generate.GenerationError) as raised:
            generate.generate_answer(self.pack, self.instructions, self.settings)
        self.assertIn("unexpected thinking output", str(raised.exception))
        self.assertNotIn("PRIVATE_THINKING_SENTINEL", str(raised.exception))

    def test_remote_incompatible_or_unbudgeted_model_is_rejected(self):
        for change in ("remote", "embedding_only", "context", "tokenizer", "template", "thinking",
                       "null_capabilities", "string_capabilities", "null_info", "list_info",
                       "null_thinking", "missing_thinking", "list_thinking", "null_values", "string_values"):
            shown = self.shown_model()
            options = deepcopy(self.settings["generation"])
            if change == "remote":
                shown["remote_host"] = "https://remote.example"
            elif change == "embedding_only":
                shown["capabilities"] = ["embedding"]
            elif change == "context":
                shown["model_info"]["qwen3.context_length"] = 8192
            elif change == "tokenizer":
                shown["model_info"]["tokenizer.ggml.model"] = "unknown"
            elif change == "template":
                shown["template"] = "x" * self.settings["generation"]["template_reserve_tokens"]
            elif change == "thinking":
                shown["thinking"]["values"] = ["low", "high"]
            elif change == "null_capabilities":
                shown["capabilities"] = None
            elif change == "string_capabilities":
                shown["capabilities"] = "completion"
            elif change == "null_info":
                shown["model_info"] = None
            elif change == "list_info":
                shown["model_info"] = []
            elif change == "null_thinking":
                shown["thinking"] = None
                options.pop("thinking_when_metadata_missing", None)
            elif change == "missing_thinking":
                shown.pop("thinking")
                options.pop("thinking_when_metadata_missing", None)
            elif change == "list_thinking":
                shown["thinking"] = []
            elif change == "null_values":
                shown["thinking"]["values"] = None
            else:
                shown["thinking"]["values"] = "true"
            with self.subTest(change=change), patch.object(generate, "installed_model_digest", return_value="d" * 64), patch.object(
                generate, "request_local_json", return_value=shown,
            ), self.assertRaises(generate.GenerationError):
                generate.inspect_model(options)

    def write_inputs(self, root):
        context = root / self.settings["answering"]["input_file"]
        context.parent.mkdir(parents=True, exist_ok=True)
        context.write_text(json.dumps(self.pack), encoding="utf-8")
        instructions = root / self.settings["answering"]["system_prompt_file"]
        instructions.parent.mkdir(parents=True, exist_ok=True)
        instructions.write_text(self.instructions, encoding="utf-8")
        return context

    def cli(self, root, args, output, *, response=None, settings=None):
        with patch.object(generate, "PROJECT_ROOT", root), patch.object(generate, "load_settings", return_value=settings or self.settings), patch.object(
            generate, "prepare_upload", return_value=self.prepared,
        ), patch.object(generate, "inspect_model", return_value=self.model_details()) as inspect, patch.object(
            generate, "request_local_json", return_value=response or self.response(),
        ) as request, patch("socket.socket.connect", side_effect=AssertionError("No network")), redirect_stdout(output):
            code = generate.main(args)
        return code, inspect.call_count, request.call_count

    def test_cli_preview_makes_no_requests_writes_no_file_and_preserves_evidence(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            context = self.write_inputs(root)
            before = context.read_bytes()
            output = io.StringIO()
            self.assertEqual(self.cli(root, [], output), (0, 0, 0))
            self.assertIn("PREVIEW ONLY", output.getvalue())
            self.assertFalse((root / self.settings["generation"]["output_file"]).exists())
            self.assertEqual(context.read_bytes(), before)

    def test_cli_success_saves_final_answer_without_thinking_and_preserves_inputs(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            context = self.write_inputs(root)
            before = context.read_bytes()
            output = io.StringIO()
            self.assertEqual(self.cli(root, ["--run"], output), (0, 1, 1))
            saved = (root / self.settings["generation"]["output_file"]).read_text(encoding="utf-8")
            self.assertNotIn("PRIVATE_THINKING_SENTINEL", saved + output.getvalue())
            self.assertNotIn("PRIVATE_PROVIDER_SENTINEL", saved + output.getvalue())
            self.assertEqual(json.loads(saved)["source_context_file"], self.settings["answering"]["input_file"])
            self.assertEqual(context.read_bytes(), before)

    def test_cli_refuses_existing_or_protected_output_without_calls(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            self.write_inputs(root)
            for name in (self.settings["generation"]["output_file"], self.settings["answering"]["input_file"],
                         self.settings["answering"]["output_file"], "README.md"):
                path = root / name
                if not path.exists():
                    path.write_text("existing report", encoding="utf-8")
                before = path.read_bytes()
                self.assertEqual(self.cli(root, ["--run", "--output", name], io.StringIO()), (1, 0, 0))
                self.assertEqual(path.read_bytes(), before)

    def test_cli_invalid_response_does_not_save_or_leak_raw_content(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            self.write_inputs(root)
            response = self.response()
            response["message"]["content"] = "PRIVATE_INVALID_CONTENT_SENTINEL"
            output = io.StringIO()
            self.assertEqual(self.cli(root, ["--run"], output, response=response), (1, 1, 1))
            self.assertNotIn("PRIVATE_INVALID_CONTENT_SENTINEL", output.getvalue())
            self.assertFalse((root / self.settings["generation"]["output_file"]).exists())

    def test_cli_timeout_explains_failure_without_saving_or_leaking_provider_details(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            context = self.write_inputs(root)
            before = context.read_bytes()
            output = io.StringIO()
            with patch.object(generate, "PROJECT_ROOT", root), patch.object(generate, "load_settings", return_value=self.settings), patch.object(
                generate, "prepare_upload", return_value=self.prepared,
            ), patch.object(generate, "inspect_model", return_value=self.model_details()), patch(
                "retail_copilot.ollama_embeddings.build_opener",
            ) as opener, patch("socket.socket.connect", side_effect=AssertionError("No network")), redirect_stdout(output):
                opener.return_value.open.side_effect = TimeoutError("PRIVATE_TIMEOUT_PROVIDER_SENTINEL")
                self.assertEqual(generate.main(["--run"]), 1)
            self.assertIn("Local Ollama timed out before a complete response arrived", output.getvalue())
            self.assertIn("No current answer was accepted or saved", output.getvalue())
            self.assertNotIn("PRIVATE_TIMEOUT_PROVIDER_SENTINEL", output.getvalue())
            self.assertFalse((root / self.settings["generation"]["output_file"]).exists())
            self.assertEqual(context.read_bytes(), before)

    def test_cli_rejects_prompt_outside_prompt_directory_before_calls(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            self.write_inputs(root)
            settings = deepcopy(self.settings)
            settings["answering"]["system_prompt_file"] = ".env"
            self.assertEqual(self.cli(root, ["--run"], io.StringIO(), settings=settings), (1, 0, 0))


if __name__ == "__main__":
    unittest.main()
