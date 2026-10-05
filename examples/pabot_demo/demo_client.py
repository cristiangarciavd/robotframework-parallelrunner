import time
from typing import Callable, Optional

from robot.api import logger


def default_log(msg, level="INFO"):
    logger.write(msg, level)


class DemoClient:
    """
    Deterministic, offline stand-in for an I/O-bound check (an API call, a DB
    query...): every call just waits ``delay`` seconds. No network involved,
    so timings are reproducible and only reflect how the work is scheduled -
    sequentially, by ParallelRunner threads, by pabot processes, or both.
    """

    def validate_item(self, item: str, delay: float = 1.0, _logger: Optional[Callable] = None, **kwargs) -> str:
        log = _logger if _logger else default_log
        log(f"Validating item {item}")
        time.sleep(float(delay))
        log(f"Item {item} is valid")
        return item
