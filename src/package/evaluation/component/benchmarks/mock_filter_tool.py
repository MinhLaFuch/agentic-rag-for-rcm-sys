"""Mock FilterTool for Planner evaluation."""

from typing import Any

from package.tools.base import Tool, ToolResult


class MockFilterTool(Tool):
    """Mock FilterTool for testing."""

    name = "FilterTool"
    description = "Retrieve candidate items with structured filters."
    input_schema = {
        "filters": {
            "domain": "str | list[str]",
            "price_min": "float",
            "price_max": "float",
            "categories_any": "list[str]",
        },
        "limit": "int",
    }
    output_schema = {"candidates": "list[dict]", "total_matches": "int"}

    def execute(self, filters: dict[str, Any] | None = None, limit: int = 10, **kwargs: Any) -> dict[str, Any]:
        filters = filters or {}
        # Return deterministic mock data
        return {
            "candidates": [
                {"item_id": f"item_{i}", "domain": "Video_Games", "title": f"Mock Item {i}", "price": 10.0 * i}
                for i in range(min(limit, 5))
            ],
            "total_matches": 5,
        }