"""Mock SearchTool for Planner evaluation."""

from typing import Any

from package.tools.base import Tool, ToolResult


class MockSearchTool(Tool):
    """Mock SearchTool for testing."""

    name = "SearchTool"
    description = "Search items by keywords."
    input_schema = {"query": "str", "limit": "int"}
    output_schema = {"candidates": "list[dict]", "total_matches": "int"}

    def execute(self, query: str, limit: int = 10, **kwargs: Any) -> dict[str, Any]:
        return {
            "candidates": [
                {"item_id": f"search_{i}", "domain": "Video_Games", "title": f"Search Result {i}", "score": 0.9 - i * 0.1}
                for i in range(min(limit, 5))
            ],
            "total_matches": 5,
        }