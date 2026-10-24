import threading
import time
from typing import Callable, Optional

from ParallelRunner import log_to_robot


class ShipmentCheckClient:
    """
    Example library for log levels, timeouts and cancellation with
    ParallelRunner. Offline and deterministic: the shipment id decides what
    happens.

    ``Check Shipment`` logs, in this order:

    - ``INFO``  ``Checking shipment <id>``
    - ``TRACE`` the request it would send (``GET /shipments/<id>``)
    - ``DEBUG`` the response it got back
    - ``HTML``  a short summary rendered as HTML in ``log.html``
    - ``WARN``  if the shipment id contains ``late``
    - ``ERROR`` (and the call fails) if the id contains ``lost``

    ``TRACE`` and ``DEBUG`` only show up in ``log.html`` with a low enough
    ``--loglevel`` (e.g. ``robot --loglevel TRACE``). A shipment id containing
    ``stuck`` waits ``stuck_seconds`` instead of ``delay``, to show what a
    timeout does to a batch with a hanging call.

    ``Track Shipment`` polls a shipment until it is delivered and stops early
    when ParallelRunner cancels it (``_cancelled``): after ``call_timeout``
    or a Robot ``[Timeout]``. ``Get Cancelled Shipments`` lists the shipments
    that stopped that way.
    """

    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    def __init__(self):
        self._cancelled_shipments = []
        self._lock = threading.Lock()

    def check_shipment(
        self,
        shipment_id: str,
        delay: float = 0.1,
        stuck_seconds: float = 60,
        _logger: Optional[Callable] = None,
        **kwargs,
    ) -> dict:
        # log_to_robot: same levels as the injected _logger, for direct calls.
        log = _logger or log_to_robot
        log(f"Checking shipment {shipment_id}")
        log(f"GET /shipments/{shipment_id}", "TRACE")
        # Stands in for the network call.
        time.sleep(stuck_seconds if "stuck" in shipment_id else delay)
        state = "lost" if "lost" in shipment_id else "late" if "late" in shipment_id else "delivered"
        log(f"Response: id={shipment_id} state={state}", "DEBUG")
        log(f"Shipment <b>{shipment_id}</b>: <i>{state}</i>", "HTML")
        if state == "late":
            log(f"Shipment {shipment_id} is late", "WARN")
        if state == "lost":
            log(f"Shipment {shipment_id} was lost", "ERROR")
            raise LookupError(f"Shipment {shipment_id} lost")
        return {"shipment_id": shipment_id, "state": state}

    def track_shipment(
        self,
        shipment_id: str,
        polls: int = 3,
        poll_interval: float = 0.1,
        _logger: Optional[Callable] = None,
        _cancelled: Optional[threading.Event] = None,
    ) -> str:
        """Polls ``polls`` times; a ``stuck`` shipment is never delivered and
        polls forever. Declaring ``_cancelled`` is what makes ParallelRunner
        pass the cancellation event."""
        log = _logger or log_to_robot
        cancelled = _cancelled or threading.Event()  # direct call: never cancelled
        poll = 0
        while "stuck" in shipment_id or poll < polls:
            poll += 1
            log(f"Poll {poll} for shipment {shipment_id}: in transit", "DEBUG")
            # Waits like time.sleep, but wakes up as soon as the call is cancelled.
            if cancelled.wait(poll_interval):
                log(f"Stopped tracking shipment {shipment_id}: cancelled", "WARN")
                with self._lock:
                    self._cancelled_shipments.append(shipment_id)
                return "cancelled"
        log(f"Shipment {shipment_id} delivered after {poll} polls")
        return "delivered"

    def get_cancelled_shipments(self, expected: int = 0, wait: float = 2) -> list:
        """Returns the shipments whose tracking was cancelled, sorted.
        Cancelled calls stop in the background, so this waits up to ``wait``
        seconds until there are at least ``expected`` of them."""
        end = time.monotonic() + wait
        while True:
            with self._lock:
                cancelled = sorted(self._cancelled_shipments)
            if len(cancelled) >= expected or time.monotonic() >= end:
                return cancelled
            time.sleep(0.02)

    def reset_cancelled_shipments(self) -> None:
        with self._lock:
            self._cancelled_shipments.clear()
