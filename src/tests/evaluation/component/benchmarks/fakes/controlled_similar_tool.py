"""Controlled mock SimilarTool for Executor evaluation."""

from typing import Any

from package.tools.base import Tool, ToolInputError


class ControlledSimilarTool(Tool):
    """Mock SimilarTool with controlled behavior."""

    name = "SimilarTool"
    description = "Retrieve items similar to given item(s)."
    input_schema = {"items": "list", "top_k": "int"}
    output_schema = {"candidates": "list", "unknown_items": "list"}

    def __init__(self, should_fail: bool = False, should_return_empty: bool = False):
        super().__init__()
        self.should_fail = should_fail
        self.should_return_empty = should_return_empty

    def execute(self, items: list[str], top_k: int = 10, **kwargs: Any) -> dict[str, Any]:
        if self.should_fail:
            raise ToolInputError("Simulated CF failure")
        if self.should_return_empty:
            return {"candidates": [], "unknown_items": []}
        return {
            "candidates": [{"item_id": f"similar_{i}", "similarity": 0.8} for i in range(min(top_k, 5))],
            "unknown_items": [],
        }