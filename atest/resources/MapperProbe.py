"""Test helper for atest/test_logger_mapper.robot.

Provides a logger mapper (`record`) that remembers every message it receives,
and a keyword (`Emit Logs`) that logs through the injected `_logger`, so the
suite can check which logger ParallelRunner actually used. No network.

Use the mapper as `atest.resources.MapperProbe.record`.
"""

import threading
from typing import Callable, List, Optional, Tuple

_RECORDED: List[Tuple[str, str]] = []
_LOCK = threading.Lock()


def record(msg: str, level: str = "INFO") -> None:
    """Logger mapper: called from worker threads, hence the lock."""
    with _LOCK:
        _RECORDED.append((level, msg))


class MapperProbe:
    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    def emit_logs(self, item: str, _logger: Optional[Callable] = None, **kwargs) -> str:
        _logger(f"info from item {item}", "INFO")
        _logger(f"warning from item {item}", "WARN")
        return item

    def clear_recorded_logs(self) -> None:
        with _LOCK:
            _RECORDED.clear()

    def get_recorded_messages(self) -> List[str]:
        with _LOCK:
            return sorted(msg for _, msg in _RECORDED)
