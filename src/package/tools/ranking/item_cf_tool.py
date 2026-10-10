"""ItemCFTool: items similar to seed item(s), from a fitted ItemKNNRecommender."""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
from scipy import sparse

from ..base import Tool, ToolCallLogger, ToolInputError, check_top_k, validate_list_like
from .._limits import ITEM_CF_DEFAULT_TOP_K, MAX_CANDIDATES
from ..corpus import ItemCorpus


class ItemCFTool(Tool):
    """
    Items similar to seed item(s), from a fitted ItemKNNRecommender's similarity
    matrix. With several seeds, similarities are summed (can exceed 1.0).
    Cross-domain by default; pass `domain` to restrict (needs a corpus).

    Note: ItemKNN keeps only the top-k neighbours per item, so a domain filter
    can return fewer than `top_k` items.
    """

    name = "ItemCFTool"
    description = "Retrieve items similar to given item(s) using item-item collaborative filtering."
    input_schema = {
        "items": "list[str]  -- namespaced seed item ids",
        "top_k": f"int (<= {MAX_CANDIDATES}, default {ITEM_CF_DEFAULT_TOP_K})",
        "domain": "str | None  -- restrict output domain; None = cross-domain",
        "exclude_input": "bool (default true)",
    }
    output_schema = {
        "candidates": "list[{item_id, similarity, domain}]  -- most similar first",
        "unknown_items": "list[str]",
        "note": "str | None  -- explanation when candidates are empty",
    }

    def __init__(
        self,
        model: Any,
        item2id: dict[str, int],
        corpus: ItemCorpus | None = None,
        logger: ToolCallLogger | None = None,
    ) -> None:
        super().__init__(logger)
        similarity = getattr(model, "similarity", None)
        if similarity is None:
            raise TypeError("model must be a fitted ItemKNNRecommender (missing `.similarity`)")
        self.similarity: sparse.csr_matrix = similarity.tocsr()
        self.item2id = item2id
        self.idx2item: dict[int, str] = {v: k for k, v in item2id.items()}
        self.corpus = corpus

    def execute(
        self,
        items: Any,
        top_k: int = ITEM_CF_DEFAULT_TOP_K,
        domain: str | None = None,
        exclude_input: bool = True,
    ) -> dict[str, Any]:
        items = validate_list_like(items, "items")
        seeds = list(dict.fromkeys(items or []))
        if not seeds:
            raise ToolInputError("`items` must contain at least one item id")
        top_k = check_top_k(top_k)
        if domain is not None and self.corpus is None:
            raise ToolInputError("domain filtering needs the tool to be built with a corpus")

        n = self.similarity.shape[0]
        seed_idx = [self.item2id[s] for s in seeds if s in self.item2id and self.item2id[s] < n]
        unknown = [s for s in seeds if s not in self.item2id or self.item2id[s] >= n]
        if not seed_idx:
            return {"candidates": [], "unknown_items": unknown, "note": "no seed item is known to the CF model"}

        # sum the seeds' similarity rows without densifying to n_items
        coo = self.similarity[seed_idx].tocoo()
        cols, inverse = np.unique(coo.col, return_inverse=True)
        scores = np.bincount(inverse, weights=coo.data, minlength=len(cols))
        if exclude_input:
            keep = ~np.isin(cols, seed_idx)
            cols, scores = cols[keep], scores[keep]

        order = np.lexsort((cols, -scores))  # score desc, then idx for determinism
        cols, scores = cols[order], scores[order]

        ids = [self.idx2item[int(c)] for c in cols if int(c) in self.idx2item]
        scores = [float(s) for c, s in zip(cols, scores) if int(c) in self.idx2item]
        domains = self.corpus.item_domains(ids) if self.corpus else {}

        candidates: list[dict[str, Any]] = []
        for item_id, score in zip(ids, scores):
            if domain is not None and domains.get(item_id) != domain:
                continue
            entry = {"item_id": item_id, "similarity": score}
            if self.corpus:
                entry["domain"] = domains.get(item_id)
            candidates.append(entry)
            if len(candidates) == top_k:
                break

        # Generate a note if candidates is empty
        note = None
        if not candidates:
            if not seed_idx:
                note = "no seed item is known to the CF model"
            elif domain is not None:
                note = f"no similar items found in domain '{domain}' (may be filtered by domain after top-k)"
            else:
                note = "no similar items found"

        return {"candidates": candidates, "unknown_items": unknown, "note": note}
