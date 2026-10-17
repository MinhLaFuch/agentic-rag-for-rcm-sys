"""Chọn vài user_id thật theo segment (demo)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def sample_users(
    fit_df: pd.DataFrame,
    user2id: dict[str, int],
    n_per_segment: int = 3,
    sparse_max: int = 5,
) -> dict[str, list[str]]:
    """Chọn vài user_id thật theo segment (cold/sparse/warm)."""
    id2user = {v: k for k, v in user2id.items()}
    num_users = len(user2id)
    hist_size = np.bincount(fit_df["user_idx"].to_numpy(), minlength=num_users)

    cold_users = [id2user[i] for i, h in enumerate(hist_size) if h == 0][:n_per_segment]
    sparse_users = [id2user[i] for i, h in enumerate(hist_size) if 0 < h <= sparse_max][:n_per_segment]
    warm_users = [id2user[i] for i, h in enumerate(hist_size) if h > sparse_max][:n_per_segment]

    return {
        "cold": cold_users,
        "sparse": sparse_users,
        "warm": warm_users,
    }
