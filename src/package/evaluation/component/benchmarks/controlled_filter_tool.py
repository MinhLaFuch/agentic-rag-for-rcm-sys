"""Controlled mock FilterTool for Executor evaluation."""

from typing import Any

from package.tools.base import Tool


class ControlledFilterTool(Tool):
    """Mock FilterTool with controlled behavior."""

    name = "FilterTool"
    description = "Retrieve candidate items with structured filters."
    input_schema = {"filters": "dict", "limit": "int"}
    output_schema = {"candidates": "list", "total_matches": "int"}

    def __init__(self, should_fail: bool = False, should_timeout: bool = False, should_return_empty: bool = False):
        super().__init__()
        self.should_fail = should_fail
        self.should_timeout = should_timeout
        self.should_return_empty = should_return_empty

    def execute(self, filters: dict[str, Any] | None = None, limit: int = 10, **kwargs: Any) -> dict[str, Any]:
        if self.should_timeout:
            import time
            time.sleep(10)  # Simulate timeout
        if self.should_fail:
            return {"ok": False, "data": {}, "error": "Simulated tool failure"}
        if self.should_return_empty:
            return {"ok": True, "data": {"candidates": [], "total_matches": 0}}
        return {
            "ok": True,
            "data": {
                "candidates": [{"item_id": f"item_{i}", "domain": "Video_Games"} for i in range(min(limit, 5))],
                "total_matches": 5,
            },
        }