import time
from typing import Callable, Optional

from robot.api import logger


def default_log(msg, level="INFO"):
    logger.write(msg, level)


class ShipmentCheckClient:
    """
    Example library for log levels and timeouts with ParallelRunner: checks a
    batch of shipments in parallel and logs at every Robot Framework level.

    Each call logs, in this order:

    - ``INFO``  ``Checking shipment <id>``
    - ``TRACE`` the request it would send (``GET /shipments/<id>``)
    - ``DEBUG`` the response it got back
    - ``HTML``  a short summary rendered as HTML in ``log.html``
    - ``WARN``  if the shipment id contains ``late``
    - ``ERROR`` (and the call fails) if the id contains ``lost``

    ``TRACE`` and ``DEBUG`` only show up in ``log.html`` with a low enough
    ``--loglevel`` (e.g. ``robot --loglevel TRACE``). A shipment id containing
    ``stuck`` waits ``stuck_seconds`` instead of ``delay``, to show what a
    Robot ``[Timeout]`` does to a batch with a hanging call. Offline and
    deterministic.
    """

    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    def check_shipment(
        self,
        shipment_id: str,
        delay: float = 0.1,
        stuck_seconds: float = 60,
        _logger: Optional[Callable] = None,
        **kwargs,
    ) -> dict:
        log = _logger if _logger else default_log
        log(f"Checking shipment {shipment_id}")
        log(f"GET /shipments/{shipment_id}", "TRACE")
        # Stands in for the network call.
        time.sleep(float(stuck_seconds if "stuck" in shipment_id else delay))
        state = "lost" if "lost" in shipment_id else "late" if "late" in shipment_id else "delivered"
        log(f"Response: id={shipment_id} state={state}", "DEBUG")
        log(f"Shipment <b>{shipment_id}</b>: <i>{state}</i>", "HTML")
        if state == "late":
            log(f"Shipment {shipment_id} is late", "WARN")
        if state == "lost":
            log(f"Shipment {shipment_id} was lost", "ERROR")
            raise LookupError(f"Shipment {shipment_id} lost")
        return {"shipment_id": shipment_id, "state": state}
