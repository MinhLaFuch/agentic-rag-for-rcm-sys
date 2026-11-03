"""Factory function for mock tools."""

from typing import Any

from .mock_filter_tool import MockFilterTool
from .mock_rank_tool import MockRankTool
from .mock_search_tool import MockSearchTool
from .mock_similar_tool import MockSimilarTool
from package.tools.base import Tool


def get_mock_tools() -> list[Tool]:
    """Return list of mock tools for Planner evaluation."""
    return [MockFilterTool(), MockSearchTool(), MockSimilarTool(), MockRankTool()]