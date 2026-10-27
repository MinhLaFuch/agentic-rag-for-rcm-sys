"""Mock tools for Planner evaluation.

These tools simulate real tools but don't require real data/LLM.
They return deterministic outputs for testing.
"""

from typing import Any

from package.tools.base import Tool, ToolResult


class MockSQLTool(Tool):
    """Mock SQLTool for testing."""

    name = "SQLTool"
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


class MockSemanticSearchTool(Tool):
    """Mock SemanticSearchTool for testing."""

    name = "SemanticSearchTool"
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


class MockItemCFTool(Tool):
    """Mock ItemCFTool for testing."""

    name = "ItemCFTool"
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


class MockRecoModelTool(Tool):
    """Mock RecoModelTool for testing."""

    name = "RecoModelTool"
    description = "Rank a candidate set for a user."
    input_schema = {"user_id": "str", "candidates": "list[str]", "top_k": "int"}
    output_schema = {"ranked": "list[dict]", "model": "str"}

    def execute(self, user_id: str, candidates: list[str], top_k: int = 10, **kwargs: Any) -> dict[str, Any]:
        return {
            "ranked": [
                {"rank": i + 1, "item_id": item_id, "score": 0.9 - i * 0.05}
                for i, item_id in enumerate(candidates[:top_k])
            ],
            "model": "mock_model",
        }


def get_mock_tools() -> list[Tool]:
    """Return list of mock tools for Planner evaluation."""
    return [MockSQLTool(), MockSemanticSearchTool(), MockItemCFTool(), MockRecoModelTool()]
