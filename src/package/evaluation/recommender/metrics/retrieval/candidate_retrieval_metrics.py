"""Metrics for ranked candidate lists produced by retrieval tools."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np


def _unique_candidates(candidates: Sequence[int], catalog_size: int) -> list[int]:
    """Preserve rank while removing padding and duplicate candidate IDs."""
    unique: list[int] = []
    seen: set[int] = set()
    for candidate in candidates:
        item = int(candidate)
        if item == -1:  # recommender padding sentinel
            continue
        if item < 0 or item >= catalog_size:
            raise ValueError(f"candidate id {item} is outside the catalog [0, {catalog_size})")
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def candidate_retrieval_metrics(
    candidate_lists: Sequence[Sequence[int]],
    targets: Sequence[set[int]],
    catalog_size: int,
) -> dict[str, Any]:
    """Summarize retrieval quality and reach for users with nonempty target sets.

    ``recall`` is macro-averaged per user. ``candidate_coverage`` is micro recall over
    all held-out user-item interactions. ``catalog_coverage`` is the fraction of the
    catalog returned at least once. Candidate lists are de-duplicated before scoring.
    """
    if len(candidate_lists) != len(targets):
        raise ValueError("candidate_lists and targets must have the same length")
    if isinstance(catalog_size, bool) or not isinstance(catalog_size, int) or catalog_size <= 0:
        raise ValueError("catalog_size must be a positive integer")

    rows = []
    for candidates, relevant in zip(candidate_lists, targets):
        relevant = set(relevant)
        if any(item < 0 or item >= catalog_size for item in relevant):
            raise ValueError("target item id is outside catalog")
        if relevant:
            rows.append((_unique_candidates(candidates, catalog_size), relevant))
    if not rows:
        return {
            "users": 0,
            "target_interactions": 0,
            "recall": None,
            "hit_rate": None,
            "candidate_coverage": None,
            "mean_candidate_set_size": None,
            "catalog_coverage": 0.0,
        }

    recalls: list[float] = []
    hit_count = 0
    target_count = 0
    returned: set[int] = set()
    sizes: list[int] = []
    for candidates, relevant in rows:
        hits = len(set(candidates) & relevant)
        recalls.append(hits / len(relevant))
        hit_count += hits
        target_count += len(relevant)
        returned.update(candidates)
        sizes.append(len(candidates))

    return {
        "users": len(rows),
        "target_interactions": target_count,
        "recall": float(np.mean(recalls)),
        "hit_rate": float(np.mean([value > 0 for value in recalls])),
        "candidate_coverage": hit_count / target_count,
        "mean_candidate_set_size": float(np.mean(sizes)),
        "catalog_coverage": len(returned) / catalog_size,
    }
