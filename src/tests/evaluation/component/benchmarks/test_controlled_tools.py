"""Regression test for Controlled* tool bug fix.

Controlled tools should raise ToolInputError when should_fail=True,
not return ok=True with error nested in data.
"""

import pytest
from package.evaluation.component.benchmarks.controlled_filter_tool import ControlledFilterTool
from package.evaluation.component.benchmarks.controlled_similar_tool import ControlledSimilarTool


def test_controlled_filter_tool_raises_on_should_fail():
    """ControlledFilterTool should raise ToolInputError when should_fail=True."""
    tool = ControlledFilterTool(should_fail=True)
    with pytest.raises(Exception):  # ToolInputError is wrapped by Tool.__call__
        tool(filters={}, limit=10)


def test_controlled_similar_tool_raises_on_should_fail():
    """ControlledSimilarTool should raise ToolInputError when should_fail=True."""
    tool = ControlledSimilarTool(should_fail=True)
    with pytest.raises(Exception):  # ToolInputError is wrapped by Tool.__call__
        tool(items=["item1"], top_k=10)


def test_controlled_filter_tool_returns_empty_on_should_return_empty():
    """ControlledFilterTool should return empty candidates when should_return_empty=True."""
    tool = ControlledFilterTool(should_return_empty=True)
    result = tool(filters={}, limit=10)
    assert result["candidates"] == []
    assert result["total_matches"] == 0


def test_controlled_similar_tool_returns_empty_on_should_return_empty():
    """ControlledSimilarTool should return empty candidates when should_return_empty=True."""
    tool = ControlledSimilarTool(should_return_empty=True)
    result = tool(items=["item1"], top_k=10)
    assert result["candidates"] == []
    assert result["unknown_items"] == []
