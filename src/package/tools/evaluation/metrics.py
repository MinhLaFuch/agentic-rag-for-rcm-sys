"""Ranking metrics computation for recommendation evaluation."""

from __future__ import annotations

import numpy as np


def ranking_metrics_at_k(
    hits: np.ndarray, num_relevant: np.ndarray, k: int
) -> dict[str, np.ndarray]:
    """Compute ranking metrics at k for multiple users."""
    if hits.ndim != 2 or hits.shape[1] < k:
        raise ValueError(f"hits must be (U, >=k={k}), got {hits.shape}")
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
