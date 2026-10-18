"""Mocked Windows power requests and local HTTP integration; no real services."""

import ctypes
import io
import unittest
from unittest.mock import Mock, call, patch
from urllib.error import URLError

from retail_copilot import ollama_embeddings, runtime_power


class RuntimePowerTests(unittest.TestCase):
    def setUp(self):
        self.active = runtime_power.ES_CONTINUOUS | runtime_power.ES_SYSTEM_REQUIRED
        self.idle = runtime_power.ES_CONTINUOUS
        self.options = {"api_base_url": "http://127.0.0.1:11434", "timeout_seconds": 30}
        self.network = patch("socket.socket.connect", side_effect=AssertionError("No network allowed"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def test_windows_api_is_typed_and_requests_only_system_awake(self):
        function = Mock(return_value=self.idle)
        library = Mock(SetThreadExecutionState=function)
        with patch.object(runtime_power.sys, "platform", "win32"), patch.object(
            runtime_power.ctypes, "WinDLL", return_value=library, create=True,
        ) as loader:
            with runtime_power.keep_system_awake():
                self.assertEqual(function.call_args_list, [call(self.active)])
        loader.assert_called_once_with("kernel32", use_last_error=True)
        self.assertEqual(function.argtypes, [ctypes.c_uint32])
        self.assertEqual(function.restype, ctypes.c_uint32)
        self.assertEqual(function.call_args_list, [call(self.active), call(self.idle)])

    def test_body_failure_restores_previous_state_and_propagates(self):
        function = Mock(return_value=self.idle)
        with patch.object(runtime_power, "_execution_state_api", return_value=function):
            with self.assertRaisesRegex(ValueError, "request failed"):
                with runtime_power.keep_system_awake():
                    raise ValueError("request failed")
        self.assertEqual(function.call_args_list, [call(self.active), call(self.idle)])

    def test_failed_power_request_is_noop_without_a_guessed_restore(self):
        for outcome in (0, OSError("unsupported power request")):
            function = Mock(side_effect=[outcome])
            with self.subTest(outcome=type(outcome).__name__), patch.object(
                runtime_power, "_execution_state_api", return_value=function,
            ):
                entered = False
                with runtime_power.keep_system_awake():
                    entered = True
                self.assertTrue(entered)
                function.assert_called_once_with(self.active)

    def test_unsupported_windows_api_and_nonwindows_are_noops(self):
        with patch.object(runtime_power.sys, "platform", "win32"), patch.object(
            runtime_power.ctypes, "WinDLL", side_effect=OSError("unavailable"), create=True,
        ):
            with runtime_power.keep_system_awake():
                pass
        with patch.object(runtime_power.sys, "platform", "linux"), patch.object(
            runtime_power.ctypes, "WinDLL", create=True,
        ) as loader:
            with runtime_power.keep_system_awake():
                pass
            loader.assert_not_called()

    def test_nested_guards_restore_outer_then_original_thread_state(self):
        state = self.idle
        def set_state(value):
            nonlocal state
            previous, state = state, value
            return previous
        function = Mock(side_effect=set_state)
        with patch.object(runtime_power, "_execution_state_api", return_value=function):
            with runtime_power.keep_system_awake():
                self.assertEqual(state, self.active)
                with runtime_power.keep_system_awake():
                    self.assertEqual(state, self.active)
                self.assertEqual(state, self.active)
            self.assertEqual(state, self.idle)
        self.assertEqual(function.call_args_list,
                         [call(self.active), call(self.active), call(self.active), call(self.idle)])

    def test_restore_failure_does_not_replace_body_exception(self):
        function = Mock(side_effect=[self.idle, OSError("restore unsupported")])
        with patch.object(runtime_power, "_execution_state_api", return_value=function):
            with self.assertRaisesRegex(ValueError, "original request failure"):
                with runtime_power.keep_system_awake():
                    raise ValueError("original request failure")

    def test_http_open_and_response_read_are_inside_power_scope(self):
        function = Mock(return_value=self.idle)
        calls = []
        class Response(io.BytesIO):
            def read(response, *args):
                self.assertEqual(function.call_count, 1)
                calls.append("read")
                return super().read(*args)
        def open_response(*args, **kwargs):
            self.assertEqual(function.call_count, 1)
            calls.append("open")
            return Response(b'{"models":[]}')
        opener = Mock()
        opener.open.side_effect = open_response
        with patch.object(runtime_power, "_execution_state_api", return_value=function), patch.object(
            ollama_embeddings, "build_opener", return_value=opener,
        ):
            self.assertEqual(ollama_embeddings.request_local_json(self.options, "/api/tags"), {"models": []})
        self.assertEqual(calls, ["open", "read"])
        self.assertEqual(function.call_args_list, [call(self.active), call(self.idle)])

    def test_failed_http_and_json_requests_restore_before_safe_error(self):
        for failure in (URLError("PRIVATE_PROVIDER_FAILURE"), b"invalid json"):
            function = Mock(return_value=self.idle)
            opener = Mock()
            if isinstance(failure, bytes):
                opener.open.return_value = io.BytesIO(failure)
            else:
                opener.open.side_effect = failure
            with self.subTest(failure=type(failure).__name__), patch.object(
                runtime_power, "_execution_state_api", return_value=function,
            ), patch.object(ollama_embeddings, "build_opener", return_value=opener):
                with self.assertRaises(ollama_embeddings.LocalOllamaError) as caught:
                    ollama_embeddings.request_local_json(self.options, "/api/tags")
                self.assertNotIn("PRIVATE_PROVIDER_FAILURE", str(caught.exception))
            self.assertEqual(function.call_args_list, [call(self.active), call(self.idle)])

    def test_invalid_url_timeout_or_route_does_not_request_power_or_http(self):
        examples = [({**self.options, "api_base_url": "http://example.invalid"}, "/api/tags"),
                    ({**self.options, "api_base_url": "http://user:secret@localhost"}, "/api/tags"),
                    ({**self.options, "timeout_seconds": 0}, "/api/tags"),
                    (self.options, "/unsupported")]
        for options, route in examples:
            with self.subTest(route=route, local=options["api_base_url"]), patch.object(
                ollama_embeddings, "keep_system_awake",
            ) as power, patch.object(ollama_embeddings, "build_opener") as opener:
                with self.assertRaises(ollama_embeddings.LocalOllamaError):
                    ollama_embeddings.request_local_json(options, route)
                power.assert_not_called()
                opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
