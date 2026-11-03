"""Mock RankTool for Planner evaluation."""

from typing import Any

from package.tools.base import Tool, ToolResult


class MockRankTool(Tool):
    """Mock RankTool for testing."""

    name = "RankTool"
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