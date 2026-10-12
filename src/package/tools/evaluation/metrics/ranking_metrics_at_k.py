"""Ranking metrics at k for many users: input validation + one call per metric."""

from __future__ import annotations

import numpy as np

from .average_precision import average_precision_at_k
from .hit_rate import hit_rate_at_k
from .mrr import mrr_at_k
from .ndcg import ndcg_at_k
from .precision import precision_at_k
from .recall import recall_at_k


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

    return {
        f"precision@{k}": precision_at_k(h),
        f"recall@{k}": recall_at_k(h, n_rel),
        f"hit_rate@{k}": hit_rate_at_k(h),
        f"ndcg@{k}": ndcg_at_k(h, n_rel),
        f"mrr@{k}": mrr_at_k(h),
        f"map@{k}": average_precision_at_k(h, n_rel),
    }
