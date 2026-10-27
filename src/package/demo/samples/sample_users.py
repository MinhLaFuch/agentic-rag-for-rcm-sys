"""Chọn vài user_id thật theo segment (demo)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from package.config import load_config


def sample_users(
    fit_df: pd.DataFrame,
    user2id: dict[str, int],
    n_per_segment: int = 3,
    sparse_max: int | None = None,
) -> dict[str, list[str]]:
    """Chọn vài user_id thật theo segment (cold/sparse/warm)."""
    if sparse_max is None:
        sparse_max = int(load_config("eval/segment_thresholds")["segment_thresholds"]["sparse_max_history"])
    if n_per_segment < 0 or sparse_max < 0:
        raise ValueError("sample size and sparse threshold must be non-negative")
    id2user = {v: k for k, v in user2id.items()}
    num_users = len(user2id)
    unique_pairs = fit_df[["user_idx", "item_idx"]].drop_duplicates()
    hist_size = np.bincount(unique_pairs["user_idx"].to_numpy(dtype=np.int64), minlength=num_users)

    cold_users = [id2user[i] for i, h in enumerate(hist_size) if h == 0][:n_per_segment]
    sparse_users = [id2user[i] for i, h in enumerate(hist_size) if 0 < h <= sparse_max][:n_per_segment]
    warm_users = [id2user[i] for i, h in enumerate(hist_size) if h > sparse_max][:n_per_segment]

    return {
        "cold": cold_users,
        "sparse": sparse_users,
        "warm": warm_users,
    }
