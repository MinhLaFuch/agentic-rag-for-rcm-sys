"""Mock SimilarTool for Planner evaluation."""

from typing import Any

from package.tools.base import Tool, ToolResult


class MockSimilarTool(Tool):
    """Mock SimilarTool for testing."""

    name = "SimilarTool"
    description = "Retrieve items similar to given item(s)."
    input_schema = {"items": "list[str]", "top_k": "int"}
    output_schema = {"candidates": "list[dict]", "unknown_items": "list[str]"}

    def execute(self, items: list[str], top_k: int = 10, **kwargs: Any) -> dict[str, Any]:
        return {
            "candidates": [
                {"item_id": f"similar_{i}", "similarity": 0.8 - i * 0.1} for i in range(min(top_k, 5))
            ],
            "unknown_items": [],
        }