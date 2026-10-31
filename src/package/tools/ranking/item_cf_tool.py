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
        "items": "list[str]  -- namespaced seed item ids (non-empty strings)",
        "top_k": f"int (<= {MAX_CANDIDATES}, default {ITEM_CF_DEFAULT_TOP_K})",
        "domain": "str | None  -- restrict output domain; None or empty string = cross-domain",
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
        # Two items sharing one (valid) index would make idx2item silently drop one of them.
        # Negative indices are not valid matrix rows; they are treated as "unknown item" in execute().
        valid_idx = [v for v in item2id.values() if v >= 0]
        if len(valid_idx) != len(set(valid_idx)):
            raise ValueError("item2id has duplicate indices: every item must map to a unique index")
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
        # Check element types BEFORE de-duplicating: dict.fromkeys needs hashable elements.
        bad = [s for s in items if not isinstance(s, str) or not s.strip()]
        if bad:
            raise ToolInputError(f"`items` must be a list of non-empty item id strings, got invalid element(s): {bad!r}")
        seeds = list(dict.fromkeys(items))
        if not seeds:
            raise ToolInputError(
                "`items` must contain at least one item id. "
                "For personalized recommendations, get seed items from MemoryTool.recent_items "
                "or from a retrieval step (SemanticSearchTool/SQLTool)."
            )
        top_k = check_top_k(top_k, name="top_k")
        if not isinstance(exclude_input, bool):
            raise ToolInputError(f"`exclude_input` must be a boolean (true/false), got {exclude_input!r}")
        if domain is not None and not isinstance(domain, str):
            raise ToolInputError(f"`domain` must be a string or null, got {type(domain).__name__}: {domain!r}")
        if domain is not None and not domain.strip():
            domain = None  # empty string = no filter (same convention as SQLTool / SemanticSearchTool)
        if domain is not None:
            if self.corpus is None:
                raise ToolInputError("domain filtering needs the tool to be built with a corpus")
            known_domains = self.corpus.domains()
            if domain not in known_domains:
                raise ToolInputError(f"unknown domain {domain!r}; available: {known_domains}")

        n = self.similarity.shape[0]
        temporal_policy = getattr(self.corpus, "_evaluation_metadata_policy", None) or {}
        visible_seed_ids = (set(self.corpus.item_domains(seeds)
                                if self.corpus is not None and temporal_policy.get("first_seen_filter") else []))
        enforce_visibility = self.corpus is not None and temporal_policy.get("first_seen_filter")

        def is_row(s: str) -> bool:  # a valid similarity row: 0 <= idx < n  (-1 would silently pick the LAST row)
            return (s in self.item2id and 0 <= self.item2id[s] < n
                    and (not enforce_visibility or s in visible_seed_ids))

        seed_idx = [self.item2id[s] for s in seeds if is_row(s)]
        unknown = [s for s in seeds if not is_row(s)]
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
            if enforce_visibility and item_id not in domains:
                continue
            if domain is not None and domains.get(item_id) != domain:
                continue
            entry = {"item_id": item_id, "similarity": score}
            if self.corpus:
                entry["domain"] = domains.get(item_id)
            candidates.append(entry)
            if len(candidates) == top_k:
                break

        # Explain an empty result. The domain filter runs over ALL of the seeds' neighbours before the
        # top_k cut, so an empty result means none of them lives in that domain (or has no neighbours).
        note = None
        if not candidates:
            if domain is not None:
                note = f"none of the seed items' similar items are in domain '{domain}'"
            else:
                note = "no similar items found"

        return {"candidates": candidates, "unknown_items": unknown, "note": note}
