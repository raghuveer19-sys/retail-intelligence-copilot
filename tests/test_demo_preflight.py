import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from retail_copilot import demo_preflight


class DemoPreflightTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        (self.root / "config").mkdir()
        (self.root / "config/settings.toml").write_text(
            '[embedding]\nmodel="embedding-test"\n[generation]\nmodel="answer-test"\n', encoding="utf-8")
        self.prepared = {"record_count": 33, "model_digest": "a" * 64}
        for name, value in (("missing_dependencies", []), ("_validate_inputs", self.prepared),
                            ("_credential_presence", {"PINECONE_API_KEY": True, "PINECONE_INDEX_HOST": True})):
            mocked = patch.object(demo_preflight, name, return_value=value)
            setattr(self, name, mocked.start())
            self.addCleanup(mocked.stop)

    def test_default_is_local_only_and_does_not_check_models(self):
        with patch.object(demo_preflight, "_installed_digest") as model:
            checks = demo_preflight.check_demo(self.root)
        self.assertTrue(all(row[1] for row in checks))
        model.assert_not_called()

    def test_missing_dependency_stops_before_inputs_credentials_or_models(self):
        self.missing_dependencies.return_value = ["streamlit"]
        with patch.object(demo_preflight, "_installed_digest") as model:
            checks = demo_preflight.check_demo(self.root, check_ollama=True)
        self.assertFalse(checks[-1][1])
        self._validate_inputs.assert_not_called()
        self._credential_presence.assert_not_called()
        model.assert_not_called()

    def test_invalid_settings_stop_before_private_configuration(self):
        (self.root / "config/settings.toml").write_text("secret-sentinel = [", encoding="utf-8")
        checks = demo_preflight.check_demo(self.root)
        self.assertFalse(checks[-1][1])
        self.assertNotIn("secret-sentinel", str(checks))
        self._credential_presence.assert_not_called()

    def test_stale_corpus_failure_does_not_expose_exception(self):
        self._validate_inputs.side_effect = ValueError("private-sentinel")
        checks = demo_preflight.check_demo(self.root)
        self.assertFalse(checks[-1][1])
        self.assertNotIn("private-sentinel", str(checks))

    def test_pinecone_key_is_required_but_host_and_openai_are_optional(self):
        self._credential_presence.return_value = {"PINECONE_API_KEY": True, "PINECONE_INDEX_HOST": False}
        self.assertTrue(all(row[1] for row in demo_preflight.check_demo(self.root)))
        self._credential_presence.return_value = {"PINECONE_API_KEY": False, "PINECONE_INDEX_HOST": True}
        self.assertFalse(demo_preflight.check_demo(self.root)[-1][1])

    def test_private_configuration_failure_is_safe(self):
        self._credential_presence.side_effect = OSError("private-key-sentinel")
        checks = demo_preflight.check_demo(self.root)
        self.assertFalse(checks[-1][1])
        self.assertNotIn("private-key-sentinel", str(checks))

    def test_model_check_only_inspects_both_models_and_matches_embedding(self):
        with patch.object(demo_preflight, "_installed_digest", side_effect=["a" * 64, "b" * 64]) as model:
            checks = demo_preflight.check_demo(self.root, check_ollama=True)
        self.assertTrue(checks[-1][1])
        self.assertEqual([call.args[0]["model"] for call in model.call_args_list], ["embedding-test", "answer-test"])

    def test_changed_or_unavailable_model_fails_without_raw_error(self):
        with patch.object(demo_preflight, "_installed_digest", return_value="b" * 64):
            self.assertFalse(demo_preflight.check_demo(self.root, check_ollama=True)[-1][1])
        with patch.object(demo_preflight, "_installed_digest", side_effect=ValueError("private-url-sentinel")):
            checks = demo_preflight.check_demo(self.root, check_ollama=True)
        self.assertFalse(checks[-1][1])
        self.assertNotIn("private-url-sentinel", str(checks))

    def test_cli_has_failure_exit_and_does_not_claim_cloud_access(self):
        output = io.StringIO()
        with patch.object(demo_preflight, "check_demo", return_value=[("Setup", False, "Check local files.")]), redirect_stdout(output):
            self.assertEqual(demo_preflight.main([]), 1)
        self.assertIn("does not verify Pinecone access/quota", output.getvalue())
        self.assertIn("No OpenAI key is required", output.getvalue())

    def test_local_model_wrapper_only_uses_existing_metadata_function(self):
        with patch("retail_copilot.ollama_embeddings.installed_model_digest", return_value="digest") as model:
            self.assertEqual(demo_preflight._installed_digest({"model": "local-test", "timeout_seconds": 300}), "digest")
        self.assertEqual(model.call_args.args[0]["timeout_seconds"], 5)

    def test_launch_refuses_occupied_port_without_reusing_or_starting_server(self):
        for code in (demo_preflight.errno.EADDRINUSE, 10048):
            output = io.StringIO()
            with patch.object(demo_preflight, "_require_free_port", side_effect=OSError(code, "private-bind-sentinel")), patch.object(demo_preflight.subprocess, "run") as run, redirect_stdout(output):
                self.assertEqual(demo_preflight.launch_demo(8501), 1)
            run.assert_not_called()
            self.assertIn("already in use", output.getvalue())
            self.assertNotIn("private-bind-sentinel", output.getvalue())

    def test_launch_refuses_indeterminate_port_without_exposing_error(self):
        output = io.StringIO()
        with patch.object(demo_preflight, "_require_free_port", side_effect=OSError("private-port-sentinel")), patch.object(demo_preflight.subprocess, "run") as run, redirect_stdout(output):
            self.assertEqual(demo_preflight.launch_demo(8501), 1)
        run.assert_not_called()
        self.assertNotIn("private-port-sentinel", output.getvalue())

    def test_launch_uses_own_python_argument_list_project_cwd_and_no_shell(self):
        with patch.object(demo_preflight, "_require_free_port"), patch.object(demo_preflight.subprocess, "run") as run, redirect_stdout(io.StringIO()):
            run.return_value.returncode = 0
            self.assertEqual(demo_preflight.launch_demo(8502), 0)
        self.assertEqual(run.call_args.args[0], [demo_preflight.sys.executable, "-m", "streamlit", "run", str(demo_preflight.PROJECT_ROOT / "app.py"), "--server.address", "127.0.0.1", "--server.port", "8502", "--server.headless", "true"])
        self.assertEqual(run.call_args.kwargs, {"cwd": demo_preflight.PROJECT_ROOT, "shell": False, "check": False})

    def test_launch_start_error_is_safe(self):
        output = io.StringIO()
        with patch.object(demo_preflight, "_require_free_port"), patch.object(demo_preflight.subprocess, "run", side_effect=OSError("private-launch-sentinel")), redirect_stdout(output):
            self.assertEqual(demo_preflight.launch_demo(8502), 1)
        self.assertNotIn("private-launch-sentinel", output.getvalue())

    def test_launch_invalid_port_never_checks_socket_or_starts_process(self):
        with patch.object(demo_preflight, "_require_free_port") as probe, patch.object(demo_preflight.subprocess, "run") as run, redirect_stdout(io.StringIO()):
            for port in (0, 65536, "8501", True):
                self.assertEqual(demo_preflight.launch_demo(port), 1)
        probe.assert_not_called()
        run.assert_not_called()

    def test_port_probe_binds_loopback_exclusively_without_listening_and_closes(self):
        with patch.object(demo_preflight.socket, "socket") as factory:
            demo_preflight._require_free_port(8502)
        factory.assert_called_once_with(demo_preflight.socket.AF_INET, demo_preflight.socket.SOCK_STREAM)
        probe = factory.return_value.__enter__.return_value
        probe.bind.assert_called_once_with(("127.0.0.1", 8502))
        probe.listen.assert_not_called()
        probe.connect.assert_not_called()
        if hasattr(demo_preflight.socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt.assert_called_once_with(demo_preflight.socket.SOL_SOCKET, demo_preflight.socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            probe.setsockopt.assert_not_called()
        factory.return_value.__exit__.assert_called_once()

    def test_cli_launch_checks_models_before_starting_and_uses_selected_port(self):
        with patch.object(demo_preflight, "check_demo", return_value=[("Setup", True, "Ready.")]) as checks, patch.object(demo_preflight, "launch_demo", return_value=0) as launch, redirect_stdout(io.StringIO()):
            self.assertEqual(demo_preflight.main(["--launch", "--port", "8502"]), 0)
        checks.assert_called_once_with(check_ollama=True)
        launch.assert_called_once_with(8502)

    def test_cli_launch_does_not_start_after_failed_preflight(self):
        with patch.object(demo_preflight, "check_demo", return_value=[("Setup", False, "Check.")]), patch.object(demo_preflight, "launch_demo") as launch, redirect_stdout(io.StringIO()):
            self.assertEqual(demo_preflight.main(["--launch"]), 1)
        launch.assert_not_called()

    def test_cli_invalid_port_is_rejected_before_preflight(self):
        with patch.object(demo_preflight, "check_demo") as checks, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as stopped:
                demo_preflight.main(["--launch", "--port", "65536"])
        self.assertEqual(stopped.exception.code, 2)
        checks.assert_not_called()


if __name__ == "__main__":
    unittest.main()
