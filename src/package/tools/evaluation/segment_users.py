"""Gán segment cold/sparse/warm cho danh sách user theo số interaction trong dữ liệu fit."""

from __future__ import annotations

import numpy as np

from ._helper import assign_segments


def segment_users(users, history_sizes: np.ndarray, sparse_max: int) -> dict[int, str]:
    """history_sizes[u] = số interaction của user u trong fit; trả về {user_idx: segment}."""
    users = list(users)
    return dict(zip(users, assign_segments(history_sizes[users], sparse_max).tolist()))
