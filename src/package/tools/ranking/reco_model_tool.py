"""RecoModelTool: rank a candidate set for a user with a recommendation model (not an LLM)."""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from ..base import Tool, ToolCallLogger, ToolInputError, candidate_ids, check_top_k
from ..corpus import ItemCorpus
from ..score import CandidateScorer


class RecoModelTool(Tool):
    """
    Rank a candidate set for a user with a recommendation model (not an LLM).
    Feed it the `candidates` from SQLTool / ItemCFTool directly.

    Leakage: the tool has no timestamp; the "as-of" time is fixed by which
    interactions the scorer's model was fitted on (train for validation runs,
    train+validation for test runs, as in scripts/run_baselines.py).

    """

    name = "RecoModelTool"
    description = (
        "Rank a candidate set for a user with a recommendation model (not an LLM). "
        "Feed it `candidates` from ItemCFTool / SemanticSearchTool / SQLTool as-is."
    )
    input_schema = {
        "user_id": "str  -- required",
        "candidates": "list[str | {item_id: str}]  -- required, e.g. \"$1.candidates\" from a retrieval step",
        "top_k": "int | None  -- default: all scorable candidates",
        "exclude_seen": "bool (default true)  -- drop items the user already interacted with",
    }
    output_schema = {
        "ranked": "list[{rank, item_id, score, domain}]  -- best first",
        "cold_start": "bool", "excluded_seen": "list[str]", "unscored_item_ids": "list[str]",
    }

    def __init__(
        self,
        scorer: CandidateScorer,
        user2id: dict[str, int],
        item2id: dict[str, int],
        corpus: ItemCorpus | None = None,
        logger: ToolCallLogger | None = None,
    ) -> None:
        super().__init__(logger)
        self.scorer = scorer
        self.user2id = user2id
        self.item2id = item2id
        self.corpus = corpus

    def execute(
        self,
        user_id: str,
        candidates: Sequence[Any],
        top_k: int | None = None,
        exclude_seen: bool = True,
    ) -> dict[str, Any]:
        ids = candidate_ids(candidates)
        if not ids:
            raise ToolInputError("`candidates` is empty")
        if top_k is not None:
            top_k = check_top_k(top_k)

        user_idx = self.user2id.get(user_id, -1)
        cold_start = not self.scorer.is_known_user(user_idx)

        scorable = [i for i in ids if i in self.item2id]
        unscored = [i for i in ids if i not in self.item2id]  # unknown to the model: reported, not hidden

        excluded_seen: list[str] = []
        if exclude_seen and not cold_start:
            seen = self.scorer.seen_items(user_idx)
            excluded_seen = [i for i in scorable if self.item2id[i] in seen]
            scorable = [i for i in scorable if self.item2id[i] not in seen]

        ranked: list[dict[str, Any]] = []
        if scorable:
            idxs = np.array([self.item2id[i] for i in scorable], dtype=np.int64)
            scores = np.asarray(self.scorer.score(user_idx, idxs), dtype=np.float64)
            order = np.argsort(-scores, kind="stable")  # ties keep input order
            domains = self.corpus.item_domains(scorable) if self.corpus else {}
            for rank, pos in enumerate(order[:top_k], start=1):
                entry = {"rank": rank, "item_id": scorable[pos], "score": float(scores[pos])}
                if self.corpus:
                    entry["domain"] = domains.get(scorable[pos])
                ranked.append(entry)

        return {
            "ranked": ranked,
            "model": self.scorer.name,
            "cold_start": cold_start,
            "excluded_seen": excluded_seen,
            "unscored_item_ids": unscored,
        }
