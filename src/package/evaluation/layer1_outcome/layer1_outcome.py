"""Layer 1: Recommendation Outcome metrics."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from package.data import ITEM_ID_SEPARATOR
from package.tools.evaluation.metrics import ranking_metrics_at_k


def score_layer1_outcome(
    request: Any,
    trajectory: dict[str, Any],
    *,
    item2id: Mapping[str, int],
    k: int,
    seen_item_ids: set[int] | None = None,
) -> dict[str, Any]:
    """
    Score recommendation outcome against ground truth targets.

    Args:
        request: AgentRequest with kind, targets, seed_item_id, category, etc.
        trajectory: Trajectory dict with 'recommended' list
        item2id: Mapping from item_id string to item_idx int
        k: Number of recommendations to consider
        seen_item_ids: Set of item_idx the user has seen in their fit history (for seen_item_rate)

    Returns:
        Dict with keys: n_recommended, precision@k, recall@k, hit_rate@k, ndcg@k, mrr@k, map@k,
                       seen_item_rate, seed_in_result, distinct_domains, distinct_main_categories
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

    # seen_item_rate: proportion of top-k items the user has seen in their fit history
    if seen_item_ids is not None and rec:
        seen_count = sum(1 for item_id in rec if item2id.get(item_id, -1) in seen_item_ids)
        row["seen_item_rate"] = seen_count / len(rec)
    else:
        row["seen_item_rate"] = None

    # seed_in_result: for 'similar' kind, whether the seed item is in top-k
    if request.kind == "similar" and request.seed_item_id and rec:
        row["seed_in_result"] = request.seed_item_id in rec
    else:
        row["seed_in_result"] = None

    # distinct_domains: number of unique domains (prefix before ITEM_ID_SEPARATOR) in top-k
    if rec:
        domains = set()
        for item_id in rec:
            if ITEM_ID_SEPARATOR in item_id:
                domain = item_id.split(ITEM_ID_SEPARATOR)[0]
                domains.add(domain)
        row["distinct_domains"] = len(domains)
    else:
        row["distinct_domains"] = None

    # distinct_main_categories: number of unique main_categories from corpus in top-k
    # Requires corpus which is not passed here; placeholder None for now
    # TODO: Implement if corpus becomes available in this layer
    row["distinct_main_categories"] = None

    return row
