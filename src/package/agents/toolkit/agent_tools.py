"""Nơi DUY NHẤT liệt kê tool mà agent được dùng: thêm/bớt tool chỉ sửa ở đây."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from .validate_tool_names import validate_tool_names  # noqa: F401  (re-export)
from ...memory.memory_tool import MemoryTool
from ...corpus import ItemCorpus
from ...tools import SimilarTool, LookupTool, RankTool, SearchTool, FilterTool
from ...tools.base import Tool


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
