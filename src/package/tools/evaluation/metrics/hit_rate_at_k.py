"""Hit rate@k."""

from __future__ import annotations

import numpy as np


def hit_rate_at_k(h: np.ndarray) -> np.ndarray:
    """1.0 when at least one of the top k items is relevant, else 0.0, per user."""
    return (h.sum(axis=1) > 0).astype(np.float64)
