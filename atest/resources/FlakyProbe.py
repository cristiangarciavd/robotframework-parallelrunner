"""Test helper for atest/test_retries.robot: keywords that fail or hang a
given number of times before they pass. No network."""

import threading
from typing import Callable, Optional


class FlakyProbe:
    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    def __init__(self):
        self._calls = {}
        self._lock = threading.Lock()

    def _count(self, key: str) -> int:
        with self._lock:
            self._calls[key] = self._calls.get(key, 0) + 1
            return self._calls[key]

    def fail_until_attempt(self, spec: str, _logger: Optional[Callable] = None) -> int:
        """``spec`` is ``key:N``: the calls for ``key`` fail until attempt N, which passes."""
        key, passing = spec.split(":")
        attempt = self._count(key)
        _logger(f"{key}: attempt {attempt}")
        if attempt < int(passing):
            raise ConnectionError(f"{key} not ready")
        return attempt

    def hang_on_first_call(self, key: str, _logger: Optional[Callable] = None, _cancelled=None) -> str:
        """The first call for ``key`` waits until it is cancelled; the next ones pass."""
        if self._count(key) == 1:
            _cancelled.wait(30)
            return "late"
        return "answered"
