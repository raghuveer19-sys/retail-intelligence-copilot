"""Keep Windows awake during a local request, without changing power settings.

The request is scoped to the calling thread and restored when the block exits.
It prevents idle system sleep only: no display, away-mode or user-input request
is added. It does not prevent an explicit user sleep action or a closed lid.
"""

from contextlib import contextmanager
import ctypes
import sys


ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def _execution_state_api():
    if sys.platform != "win32":
        return None
    try:
        function = ctypes.WinDLL("kernel32", use_last_error=True).SetThreadExecutionState
        function.argtypes = [ctypes.c_uint32]
        function.restype = ctypes.c_uint32
        return function
    except (AttributeError, OSError, TypeError):
        return None


@contextmanager
def keep_system_awake():
    """Hold an idle-sleep request for this block; unsupported systems are a no-op."""
    function = _execution_state_api()
    previous = 0
    if function is not None:
        try:
            previous = function(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        except (OSError, TypeError, ctypes.ArgumentError):
            previous = 0
    try:
        yield
    finally:
        if previous:
            try:
                # Restoring the previous state also preserves an outer guard.
                function(previous | ES_CONTINUOUS)
            except (OSError, TypeError, ctypes.ArgumentError):
                # Power-management support must not replace a request error.
                pass
