"""Nơi DUY NHẤT liệt kê tool mà agent được dùng: thêm/bớt tool chỉ sửa ở đây."""

from __future__ import annotations

from dataclasses import dataclass

from ...memory.memory_tool import MemoryTool
from ...tools import ItemCFTool, ItemCorpus, QueryTool, RecoModelTool, SemanticSearchTool, SQLTool
from ...tools.base import Tool


@dataclass
class AgentTools:
    item_cf: ItemCFTool
    reco: RecoModelTool
    query: QueryTool
    search: SemanticSearchTool
    sql: SQLTool
    memory: MemoryTool

    def for_planner(self) -> list[Tool]:
        return [self.item_cf, self.reco, self.query, self.search, self.sql]

    def for_planner_memory(self) -> list[Tool]:
        return [*self.for_planner(), self.memory]
