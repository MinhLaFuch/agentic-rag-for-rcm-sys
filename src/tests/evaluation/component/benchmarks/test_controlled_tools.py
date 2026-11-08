"""Regression test for Controlled* tool bug fix.

Controlled tools should return ToolResult with ok=False when should_fail=True,
not return ok=True with error nested in data.
"""

import pytest
from tests.evaluation.component.benchmarks.fakes.controlled_filter_tool import ControlledFilterTool
from tests.evaluation.component.benchmarks.fakes.controlled_similar_tool import ControlledSimilarTool


def test_controlled_filter_tool_returns_ok_false_on_should_fail():
    """ControlledFilterTool should return ToolResult with ok=False when should_fail=True."""
    tool = ControlledFilterTool(should_fail=True)
    result = tool(filters={}, limit=10)
    assert result.ok is False
    assert result.error is not None


def test_controlled_similar_tool_returns_ok_false_on_should_fail():
    """ControlledSimilarTool should return ToolResult with ok=False when should_fail=True."""
    tool = ControlledSimilarTool(should_fail=True)
    result = tool(items=["item1"], top_k=10)
    assert result.ok is False
    assert result.error is not None


def test_controlled_filter_tool_returns_empty_on_should_return_empty():
    """ControlledFilterTool should return empty candidates when should_return_empty=True."""
    tool = ControlledFilterTool(should_return_empty=True)
    result = tool(filters={}, limit=10)
    assert result.data["candidates"] == []
    assert result.data["total_matches"] == 0


def test_controlled_similar_tool_returns_empty_on_should_return_empty():
    """ControlledSimilarTool should return empty candidates when should_return_empty=True."""
    tool = ControlledSimilarTool(should_return_empty=True)
    result = tool(items=["item1"], top_k=10)
    assert result.data["candidates"] == []
    assert result.data["unknown_items"] == []
