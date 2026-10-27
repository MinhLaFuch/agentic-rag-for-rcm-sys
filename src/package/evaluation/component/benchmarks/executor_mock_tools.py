"""Controlled mock tools for Executor evaluation.

These tools can be configured to:
- Fail on specific inputs
- Timeout
- Return empty output
- Return invalid schema
"""

from typing import Any

from package.tools.base import Tool


class ControlledSQLTool(Tool):
    """Mock SQLTool with controlled behavior."""

    name = "SQLTool"
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


class ControlledItemCFTool(Tool):
    """Mock ItemCFTool with controlled behavior."""

    name = "ItemCFTool"
    description = "Retrieve items similar to given item(s)."
    input_schema = {"items": "list", "top_k": "int"}
    output_schema = {"candidates": "list", "unknown_items": "list"}

    def __init__(self, should_fail: bool = False, should_return_empty: bool = False):
        super().__init__()
        self.should_fail = should_fail
        self.should_return_empty = should_return_empty

    def execute(self, items: list[str], top_k: int = 10, **kwargs: Any) -> dict[str, Any]:
        if self.should_fail:
            return {"ok": False, "data": {}, "error": "Simulated CF failure"}
        if self.should_return_empty:
            return {"ok": True, "data": {"candidates": [], "unknown_items": []}}
        return {
            "ok": True,
            "data": {
                "candidates": [{"item_id": f"similar_{i}", "similarity": 0.8} for i in range(min(top_k, 5))],
                "unknown_items": [],
            },
        }


def get_controlled_tools(config: dict[str, Any] | None = None) -> list[Tool]:
    """Return controlled mock tools based on config."""
    config = config or {}
    return [
        ControlledSQLTool(
            should_fail=config.get("sql_fail", False),
            should_timeout=config.get("sql_timeout", False),
            should_return_empty=config.get("sql_empty", False),
        ),
        ControlledItemCFTool(
            should_fail=config.get("cf_fail", False),
            should_return_empty=config.get("cf_empty", False),
        ),
    ]
