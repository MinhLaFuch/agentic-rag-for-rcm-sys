"""Ranking metrics computation for recommendation evaluation."""

from __future__ import annotations

import numpy as np


def ranking_metrics_at_k(
    hits: np.ndarray, num_relevant: np.ndarray, k: int
) -> dict[str, np.ndarray]:
    """Compute ranking metrics at k for multiple users.

    hits[u, r] is truthy when the item recommended at rank r+1 (0-based column r) is relevant to user u;
    a padded slot must already be False. ``num_relevant[u]`` is the user's total number of relevant items (> 0).
    Precision@k divides by k (a short list is penalised); recall@k divides by num_relevant; NDCG/AP use
    min(num_relevant, k) as the ideal length.
    """
    if isinstance(k, (bool, np.bool_)) or not isinstance(k, (int, np.integer)) or k < 1:
        raise ValueError(f"k must be a positive integer, got {k!r}")
    if hits.ndim != 2 or hits.shape[1] < k:
        raise ValueError(f"hits must be (U, >=k={k}), got {hits.shape}")
    num_relevant = np.asarray(num_relevant)
    if num_relevant.shape != (hits.shape[0],):
        raise ValueError(f"num_relevant must have shape ({hits.shape[0]},), got {num_relevant.shape}")
    if hits.size and (hits.min() < 0 or hits.max() > 1):
        raise ValueError("hits must contain only 0/1 (False/True) values")
    if np.any(num_relevant <= 0):
        raise ValueError("num_relevant must be > 0 for every evaluated user")

    h = hits[:, :k].astype(np.float64)
    n_rel = num_relevant.astype(np.float64)
    ranks = np.arange(1, k + 1, dtype=np.float64)

    num_hits = h.sum(axis=1)

    precision = num_hits / k
    recall = num_hits / n_rel
    hit_rate = (num_hits > 0).astype(np.float64)

    discounts = 1.0 / np.log2(ranks + 1.0)
    dcg = (h * discounts).sum(axis=1)
    ideal_len = np.minimum(n_rel, k).astype(np.int64)
    cum_discounts = np.cumsum(discounts)
    idcg = cum_discounts[ideal_len - 1]
    ndcg = dcg / idcg

    first_hit = np.argmax(h > 0, axis=1)
    mrr = np.where(num_hits > 0, 1.0 / (first_hit + 1.0), 0.0)

    precision_at_rank = np.cumsum(h, axis=1) / ranks
    ap = (precision_at_rank * h).sum(axis=1) / np.minimum(n_rel, k)

    return {
        f"precision@{k}": precision,
        f"recall@{k}": recall,
        f"hit_rate@{k}": hit_rate,
        f"ndcg@{k}": ndcg,
        f"mrr@{k}": mrr,
        f"map@{k}": ap,
    }
