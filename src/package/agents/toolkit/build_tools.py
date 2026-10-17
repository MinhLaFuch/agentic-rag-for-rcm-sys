"""Xây dựng AgentTools từ các dependencies."""

from __future__ import annotations

import pandas as pd

from .agent_tools import AgentTools
from ...memory.memory_tool import MemoryTool
from ...tools import ItemCFTool, ItemCorpus, QueryTool, RecoModelTool, SemanticSearchTool
from ...tools.score import CandidateScorer
from ...tools.recommenders import Recommender


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
