"""Retries of failed calls in `Run Parallel Scenarios`: the ``call_retries``,
``retry_delay`` and ``retry_backoff`` arguments.

This module only decides *whether* and *when* a call is retried, and what is
logged between attempts. Running the attempts on the worker threads (and
retrying calls that exceeded ``call_timeout``) is done by
``ParallelRunner._run_in_threads``.
"""

import math
from dataclasses import dataclass
from typing import Any

from robot.errors import DataError
from robot.utils import secs_to_timestr, timestr_to_secs

DEFAULT_RETRY_DELAY = 1.0


def _not_given(value: Any) -> bool:
    """None, an empty string or "None" (any case), like in parallel_library."""
    return value is None or (isinstance(value, str) and value.strip().upper() in ("", "NONE"))


@dataclass(frozen=True)
class RetryPolicy:
    """How often and how long apart a failed call is tried again.

    ``retries`` extra attempts after the first one; before attempt ``n + 1``
    the call waits ``delay * backoff ** (n - 1)`` seconds (``backoff=1``: a
    fixed delay; ``backoff=2``: 1 s, 2 s, 4 s...).
    """

    retries: int = 0
    delay: float = DEFAULT_RETRY_DELAY
    backoff: float = 1.0

    @property
    def attempts(self) -> int:
        """Maximum number of attempts per call."""
        return self.retries + 1

    def can_retry(self, attempt: int) -> bool:
        """Whether a call whose attempt number ``attempt`` (1-based) failed may run again."""
        return attempt < self.attempts

    def delay_after(self, attempt: int) -> float:
        """Seconds to wait between failed attempt ``attempt`` and the next one."""
        return self.delay * self.backoff ** (attempt - 1)

    def failed_message(self, attempt: int, error: str) -> str:
        return f"Attempt {attempt} of {self.attempts} failed: {error}; {self._retrying(attempt)}"

    def timed_out_message(self, attempt: int, duration: str) -> str:
        return (
            f"Attempt {attempt} of {self.attempts} timed out after {duration} (call_timeout), "
            f"it keeps running in the background; {self._retrying(attempt)}"
        )

    def _retrying(self, attempt: int) -> str:
        delay = self.delay_after(attempt)
        return f"retrying in {secs_to_timestr(delay)}" if delay > 0 else "retrying now"

    @classmethod
    def from_arguments(cls, call_retries: Any = None, retry_delay: Any = None, retry_backoff: Any = None) -> "RetryPolicy":
        """Validates the keyword arguments, in Robot's formats: ``call_retries``
        a whole number, ``retry_delay`` a Robot time (``1s``, ``500ms``),
        ``retry_backoff`` a number. Not given: no retries, a 1 second delay,
        no backoff. An invalid value raises ``ValueError`` before anything runs."""
        return cls(
            retries=cls._resolve_retries(call_retries),
            delay=cls._resolve_delay(retry_delay),
            backoff=cls._resolve_backoff(retry_backoff),
        )

    @staticmethod
    def _resolve_retries(value: Any) -> int:
        if _not_given(value):
            return 0
        try:
            # Through str: rejects 1.5 (and True) instead of truncating it.
            retries = int(str(value).strip())
        except ValueError:
            retries = -1
        if retries < 0:
            raise ValueError(f"Invalid call_retries {value!r}: expected a whole number of at least 0.")
        return retries

    @staticmethod
    def _resolve_delay(value: Any) -> float:
        if _not_given(value):
            return DEFAULT_RETRY_DELAY
        try:
            seconds = timestr_to_secs(value)
        except (ValueError, DataError) as error:
            raise ValueError(f"Invalid retry_delay {value!r}: {error}") from None
        if seconds < 0:
            raise ValueError(f"retry_delay can't be negative, got {value!r}.")
        return seconds

    @staticmethod
    def _resolve_backoff(value: Any) -> float:
        if _not_given(value):
            return 1.0
        try:
            backoff = float(str(value).strip())
        except ValueError:
            raise ValueError(f"Invalid retry_backoff {value!r}: expected a number of at least 1.") from None
        if not 1 <= backoff < math.inf:  # also rejects NaN
            raise ValueError(f"retry_backoff must be at least 1, got {value!r}.")
        return backoff


NO_RETRIES = RetryPolicy()
