"""Nơi DUY NHẤT liệt kê tool mà agent được dùng: thêm/bớt tool chỉ sửa ở đây."""

from __future__ import annotations

from dataclasses import dataclass

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

    def for_planner(self) -> list[Tool]:
        return [self.item_cf, self.reco, self.query, self.search, self.sql]

    def for_planner_memory(self) -> list[Tool]:
        return [*self.for_planner(), self.memory]
