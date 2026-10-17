"""Recall@k."""

from __future__ import annotations

import numpy as np


def recall_at_k(h: np.ndarray, num_relevant: np.ndarray) -> np.ndarray:
    """Hits in the top k divided by the user's total number of relevant items.

    ``h`` is the (U, k) float 0/1 matrix of the top-k slots; ``num_relevant`` is float64, shape (U,), all > 0.
    """
    return h.sum(axis=1) / num_relevant
