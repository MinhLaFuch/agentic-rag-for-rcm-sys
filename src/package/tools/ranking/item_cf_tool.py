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
        
        # Check for duplicate indices (two items mapping to the same index)
        seen_indices = {}
        for item_id, idx in item2id.items():
            if idx in seen_indices:
                raise ValueError(
                    f"item2id has duplicate index {idx} for items '{seen_indices[idx]}' and '{item_id}'. "
                    "Each item must have a unique index."
                )
            seen_indices[idx] = item_id
        
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
        # Validate exclude_input is a boolean
        if not isinstance(exclude_input, bool):
            raise ToolInputError(
                f"`exclude_input` must be a boolean (True/False), got {type(exclude_input).__name__}: {exclude_input!r}"
            )
        
        # Validate domain is a string if provided
        if domain is not None and not isinstance(domain, str):
            raise ToolInputError(
                f"`domain` must be a string or None, got {type(domain).__name__}: {domain!r}"
            )
        
        items = validate_list_like(items, "items")
        # Validate each item is a non-empty string
        for i, item in enumerate(items):
            if not isinstance(item, str) or not item.strip():
                raise ToolInputError(
                    f"`items[{i}]` must be a non-empty string, got {type(item).__name__}: {item!r}"
                )
        seeds = list(dict.fromkeys(items or []))
        if not seeds:
            raise ToolInputError("`items` must contain at least one item id")
        top_k = check_top_k(top_k, name="top_k")
        if domain is not None and self.corpus is None:
            raise ToolInputError("domain filtering needs the tool to be built with a corpus")

        n = self.similarity.shape[0]
        seed_idx = [self.item2id[s] for s in seeds if s in self.item2id and 0 <= self.item2id[s] < n]
        unknown = [s for s in seeds if s not in self.item2id or not (0 <= self.item2id[s] < n)]
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
                note = f"no similar items found in domain '{domain}'"
            else:
                note = "no similar items found"

        return {"candidates": candidates, "unknown_items": unknown, "note": note}
