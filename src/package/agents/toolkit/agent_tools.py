"""Nơi DUY NHẤT liệt kê tool mà agent được dùng: thêm/bớt tool chỉ sửa ở đây."""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass

from ...memory.memory_tool import MemoryTool
from ...corpus import ItemCorpus
from ...tools import SimilarTool, LookupTool, RankTool, SearchTool, FilterTool
from ...tools.base import Tool

# Tên class tool hợp lệ cho tool subset (config exclude_tools / YAML overlay).
_VALID_TOOL_NAMES = frozenset(
    cls.__name__
    for cls in (SimilarTool, RankTool, LookupTool, SearchTool, FilterTool, MemoryTool)
)


def validate_tool_names(names: Iterable[str]) -> list[str]:
    """Validate danh sách tên tool; raise ValueError kèm tên hợp lệ nếu sai."""
    out = [str(n) for n in names]
    unknown = sorted(set(out) - _VALID_TOOL_NAMES)
    if unknown:
        raise ValueError(
            f"Unknown tool name(s) {unknown}; valid: {sorted(_VALID_TOOL_NAMES)}"
        )
    return out


@dataclass
class AgentTools:
    item_cf: SimilarTool
    reco: RankTool
    query: LookupTool
    search: SearchTool
    sql: FilterTool
    memory: MemoryTool

    def _exclude(self, tools: list[Tool], exclude_tools: Collection[str]) -> list[Tool]:
        if not exclude_tools:
            return tools
        return [t for t in tools if type(t).__name__ not in exclude_tools]

    def for_planner(self, exclude_tools: Collection[str] = ()) -> list[Tool]:
        return self._exclude(
            [self.item_cf, self.reco, self.query, self.search, self.sql], exclude_tools
        )

    def for_planner_memory(self, exclude_tools: Collection[str] = ()) -> list[Tool]:
        return [
            *self.for_planner(exclude_tools=exclude_tools),
            *self._exclude([self.memory], exclude_tools),
        ]
