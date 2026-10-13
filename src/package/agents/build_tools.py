"""Nơi DUY NHẤT liệt kê tool mà agent được dùng: thêm/bớt tool chỉ sửa ở đây."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..memory.memory_tool import MemoryTool
from ..tools import ItemCFTool, ItemCorpus, QueryTool, RecoModelTool, SemanticSearchTool
from ..tools.base import Tool
from ..tools.score import CandidateScorer
from ..tools.recommenders import Recommender


@dataclass
class AgentTools:
    item_cf: ItemCFTool
    reco: RecoModelTool
    query: QueryTool
    search: SemanticSearchTool
    memory: MemoryTool

    def for_planner(self) -> list[Tool]:
        return [self.item_cf, self.reco, self.query, self.search]

    def for_planner_memory(self) -> list[Tool]:
        return [*self.for_planner(), self.memory]


def build_tools(
    knn: Recommender,
    scorer: CandidateScorer,
    user2id: dict[str, int],
    item2id: dict[str, int],
    interactions: pd.DataFrame,
    corpus: ItemCorpus,
    logger=None,
    as_of_timestamp: int | None = None,
) -> AgentTools:
    """knn: nguồn similarity cho ItemCFTool; scorer: cho RecoModelTool; as_of_timestamp: mốc chống leakage cho MemoryTool."""
    return AgentTools(
        item_cf=ItemCFTool(knn, item2id, corpus=corpus, logger=logger),
        reco=RecoModelTool(scorer, user2id, item2id, corpus=corpus, logger=logger),
        query=QueryTool(corpus, logger=logger),
        search=SemanticSearchTool(corpus, logger=logger),
        memory=MemoryTool(interactions, user2id, item2id, corpus, logger=logger, as_of_timestamp=as_of_timestamp),
    )
