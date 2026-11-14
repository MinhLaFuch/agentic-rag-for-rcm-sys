"""Tool subset (exclude_tools) trên AgentTools — default không đổi."""

from __future__ import annotations

import pytest

from package.agents.toolkit.agent_tools import AgentTools, validate_tool_names


def _stub(name: str):
    return type(name, (), {})()


def _tools() -> AgentTools:
    return AgentTools(
        item_cf=_stub("SimilarTool"),
        reco=_stub("RankTool"),
        query=_stub("LookupTool"),
        search=_stub("SearchTool"),
        sql=_stub("FilterTool"),
        memory=_stub("MemoryTool"),
    )


def _names(tools) -> list[str]:
    return [type(t).__name__ for t in tools]


def test_default_unchanged():
    tools = _tools()
    assert _names(tools.for_planner()) == ["SimilarTool", "RankTool", "LookupTool", "SearchTool", "FilterTool"]
    assert _names(tools.for_planner_memory()) == [
        "SimilarTool", "RankTool", "LookupTool", "SearchTool", "FilterTool", "MemoryTool",
    ]


def test_exclude_rank_tool():
    tools = _tools()
    assert _names(tools.for_planner(exclude_tools=["RankTool"])) == [
        "SimilarTool", "LookupTool", "SearchTool", "FilterTool",
    ]
    assert _names(tools.for_planner_memory(exclude_tools=["RankTool"])) == [
        "SimilarTool", "LookupTool", "SearchTool", "FilterTool", "MemoryTool",
    ]


def test_exclude_memory_tool():
    tools = _tools()
    assert "MemoryTool" not in _names(tools.for_planner_memory(exclude_tools=["MemoryTool"]))


def test_validate_tool_names_ok_and_error():
    assert validate_tool_names(["RankTool", "MemoryTool"]) == ["RankTool", "MemoryTool"]
    with pytest.raises(ValueError, match="Unknown tool name"):
        validate_tool_names(["NotATool"])
