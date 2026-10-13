"""MAP@k (average precision per user)."""

from __future__ import annotations

import numpy as np


def average_precision_at_k(h: np.ndarray, num_relevant: np.ndarray) -> np.ndarray:
    """Mean of precision@rank over the ranks of the hits, divided by min(num_relevant, k).

    ``h`` is the (U, k) float 0/1 matrix; ``num_relevant`` is float64, shape (U,), all > 0.
    """
    k = h.shape[1]
    ranks = np.arange(1, k + 1, dtype=np.float64)
    precision_at_rank = np.cumsum(h, axis=1) / ranks
    return (precision_at_rank * h).sum(axis=1) / np.minimum(num_relevant, k)
