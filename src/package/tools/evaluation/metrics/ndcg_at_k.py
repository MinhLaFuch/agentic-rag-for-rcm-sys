"""NDCG@k."""

from __future__ import annotations

import numpy as np


def ndcg_at_k(h: np.ndarray, num_relevant: np.ndarray) -> np.ndarray:
    """Binary-gain NDCG: DCG of the list divided by the DCG of an ideal list.

    The ideal list has min(num_relevant, k) relevant items at the top. ``h`` is the (U, k) float 0/1 matrix;
    ``num_relevant`` is float64, shape (U,), all > 0.
    """
    k = h.shape[1]
    ranks = np.arange(1, k + 1, dtype=np.float64)
    discounts = 1.0 / np.log2(ranks + 1.0)
    dcg = (h * discounts).sum(axis=1)
    ideal_len = np.minimum(num_relevant, k).astype(np.int64)
    idcg = np.cumsum(discounts)[ideal_len - 1]
    return dcg / idcg
