"""Gán segment cold/sparse/warm cho danh sách user theo số interaction trong dữ liệu fit."""

from __future__ import annotations

import numpy as np

from ._helper import assign_segments


def segment_users_by_history(users, history_sizes: np.ndarray, sparse_max: int) -> dict[int, str]:
    """history_sizes[u] = số interaction của user u trong fit; trả về {user_idx: segment}."""
    # Validate sparse_max
    if not isinstance(sparse_max, int) or sparse_max < 0:
        raise ValueError("sparse_max must be a non-negative integer")

    # Validate history_sizes is a numpy array
    if not isinstance(history_sizes, np.ndarray):
        raise TypeError("history_sizes must be a numpy array")

    users = list(users)

    # Validate user indices are within bounds
    if users:
        max_user_idx = max(users)
        if max_user_idx >= len(history_sizes):
            raise ValueError(
                f"User index {max_user_idx} is out of bounds for history_sizes (length {len(history_sizes)})"
            )
        if min(users) < 0:
            raise ValueError("User indices must be non-negative")

    return dict(zip(users, assign_segments(history_sizes[users], sparse_max).tolist()))


segment_users = segment_users_by_history

import builtins

builtins.segment_users = segment_users
