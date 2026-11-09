"""Candidate retrieval quality by target-item familiarity."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from .candidate_retrieval_metrics import candidate_retrieval_metrics


def item_familiarity_metrics(
    candidate_lists: Sequence[Sequence[int]],
    targets: Sequence[set[int]],
    fit_item_seen: np.ndarray,
) -> dict[str, dict[str, Any]]:
    """Break retrieval metrics out by whether target items occur in fit data."""
    if len(candidate_lists) != len(targets):
        raise ValueError("candidate_lists and targets must have the same length")
    seen = np.asarray(fit_item_seen, dtype=bool)
    result: dict[str, dict[str, Any]] = {}
    for label, is_seen in (("warm_item", True), ("cold_item", False)):
        filtered: list[set[int]] = []
        for relevant in targets:
            if any(item < 0 or item >= len(seen) for item in relevant):
                raise ValueError("target item id is outside fit_item_seen")
            filtered.append({item for item in relevant if bool(seen[item]) == is_seen})
        result[label] = candidate_retrieval_metrics(candidate_lists, filtered, max(1, len(seen)))
    return result
