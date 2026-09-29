"""Helper functions for evaluation."""

from __future__ import annotations

import numpy as np


def assign_segments(history_sizes: np.ndarray, sparse_max: int) -> np.ndarray:
    """Assign user segments based on interaction history size."""
    return np.where(
        history_sizes == 0, "cold", np.where(history_sizes <= sparse_max, "sparse", "warm")
    )
