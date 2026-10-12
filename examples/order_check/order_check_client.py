import threading
import time
from typing import Callable, Optional

from robot.api import logger


def default_log(msg, level="INFO"):
    logger.write(msg, level)


class OrderCheckClient:
    """
    Example library for how ParallelRunner handles calls that fail: checks a
    batch of orders in parallel, where some orders are broken on purpose.

    An order id containing ``missing`` raises (as a real API would return a
    404), one containing ``late`` logs a warning but passes, any other id
    passes. Each call waits ``delay`` seconds to stand in for I/O. Offline and
    deterministic, so the failures are always the same ones.

    ``Get Checked Orders`` returns every order that was actually checked, to
    show that one failing call never stops the others: `Run Parallel
    Scenarios` waits for all of them before it fails.
    """

    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    def __init__(self):
        self._checked = []
        self._lock = threading.Lock()

    def check_order(self, order_id: str, delay: float = 0.1, _logger: Optional[Callable] = None, **kwargs) -> dict:
        log = _logger if _logger else default_log
        log(f"Checking order {order_id}")
        time.sleep(float(delay))
        # Called from several threads at once: shared state needs a lock.
        with self._lock:
            self._checked.append(order_id)
        if "missing" in order_id:
            log(f"Order {order_id} does not exist", "WARN")
            raise LookupError(f"Order {order_id} not found")
        if "late" in order_id:
            log(f"Order {order_id} is late", "WARN")
        log(f"Order {order_id} is OK")
        return {"order_id": order_id, "state": "late" if "late" in order_id else "ok"}

    def reset_checked_orders(self) -> None:
        with self._lock:
            self._checked.clear()

    def get_checked_orders(self) -> list:
        with self._lock:
            return sorted(self._checked)
