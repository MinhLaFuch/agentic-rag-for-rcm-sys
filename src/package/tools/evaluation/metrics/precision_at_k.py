"""Precision@k."""

from __future__ import annotations

import numpy as np


def precision_at_k(h: np.ndarray) -> np.ndarray:
    """Hits in the top k divided by k, per user (a short or padded list is penalised).

    ``h`` is the (U, k) float 0/1 matrix of the top-k slots.
    """
    return h.sum(axis=1) / h.shape[1]
