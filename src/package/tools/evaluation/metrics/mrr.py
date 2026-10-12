"""MRR@k."""

from __future__ import annotations

import numpy as np


def mrr_at_k(h: np.ndarray) -> np.ndarray:
    """Reciprocal rank of the first relevant item in the top k (0.0 when there is none), per user."""
    first_hit = np.argmax(h > 0, axis=1)
    return np.where(h.sum(axis=1) > 0, 1.0 / (first_hit + 1.0), 0.0)
