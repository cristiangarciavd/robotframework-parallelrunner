"""Test helper for atest/test_thread_workers.robot: measures how many calls
run at once. No network."""

import threading
import time
from typing import Callable, Optional


class ConcurrencyProbe:
    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    def __init__(self):
        self._lock = threading.Lock()
        self._running = 0
        self.max_running = 0

    def reset_concurrency(self):
        """Forgets the highest concurrency seen so far."""
        with self._lock:
            self._running = 0
            self.max_running = 0

    def max_concurrency(self) -> int:
        """Returns the highest number of `Busy Call` calls seen running at once."""
        return self.max_running

    def busy_call(self, item, seconds: float = 0.05, tag: str = "", _logger: Optional[Callable] = None) -> str:
        """Runs for `seconds` while counting how many calls run at the same time."""
        with self._lock:
            self._running += 1
            self.max_running = max(self.max_running, self._running)
        try:
            time.sleep(seconds)
        finally:
            with self._lock:
                self._running -= 1
        return f"{item}{tag}"
