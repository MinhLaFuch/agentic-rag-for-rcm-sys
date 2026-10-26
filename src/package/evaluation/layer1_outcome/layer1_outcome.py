"""Layer 1: Recommendation Outcome metrics."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from package.tools.evaluation.metrics import ranking_metrics_at_k


def score_layer1_outcome(
    request: Any,
    trajectory: dict[str, Any],
    *,
    item2id: Mapping[str, int],
    k: int,
) -> dict[str, Any]:
    """
    Score recommendation outcome against ground truth targets.

    Returns:
        Dict with keys: n_recommended, precision@k, recall@k, hit_rate@k, ndcg@k, mrr@k, map@k
    """
    # Deduplicate recommendations and limit to k
    rec = list(dict.fromkeys(trajectory["recommended"]))[:k]
    
    row: dict[str, Any] = {"n_recommended": len(rec)}
    
    # Calculate ranking metrics only for non-ambiguous requests with targets
    ranking_keys = (f"precision@{k}", f"recall@{k}", f"hit_rate@{k}", f"ndcg@{k}", f"mrr@{k}", f"map@{k}")
    if request.kind != "ambiguous" and request.targets:
        relevant = set(request.targets)
        hits = np.zeros((1, k))
        for rank, item_id in enumerate(rec):
            hits[0, rank] = float(item2id.get(item_id, -1) in relevant)
        metrics = ranking_metrics_at_k(hits, np.array([len(relevant)]), k)
        row.update({key: float(metrics[key][0]) for key in ranking_keys})
    else:
        row.update({key: None for key in ranking_keys})
    
    return row
