"""Test helper for atest/test_keyword_calls.robot: keywords whose arguments
and names exercise how ParallelRunner finds and calls a keyword. No network."""

from typing import Callable, Optional

from robot.api.deco import keyword


class KeywordProbe:
    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    def describe_arguments(
        self, item: int, delay: float = 0.1, enabled: bool = False, tags: Optional[list] = None,
        _logger: Optional[Callable] = None,
    ) -> dict:
        """Returns each argument's value and type name, to compare a direct call with a parallel one."""
        values = {"item": item, "delay": delay, "enabled": enabled, "tags": tags}
        return {name: [value, type(value).__name__] for name, value in values.items()}

    @keyword("Check Order Status")
    def _status_of(self, order_id, _logger: Optional[Callable] = None) -> str:
        return f"status of {order_id}"
