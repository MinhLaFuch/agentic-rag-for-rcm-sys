"""Build target-bearing evaluation users with segments from train history."""

from __future__ import annotations

import numpy as np
import pandas as pd


def build_evaluation_cohort(train: pd.DataFrame, targets: pd.DataFrame, sparse_max: int) -> pd.DataFrame:
    """Return one row per target-bearing user, segmented by unique train items."""
    required = {"user_id", "parent_asin"}
    if required - set(train.columns) or required - set(targets.columns):
        raise ValueError("train and targets must contain user_id and parent_asin")
    history = train.groupby("user_id")["parent_asin"].nunique()
    cohort = targets[["user_id"]].drop_duplicates().copy()
    cohort["history_size"] = cohort.user_id.map(history).fillna(0).astype("int64")
    cohort["segment"] = np.where(cohort.history_size.eq(0), "cold",
                                 np.where(cohort.history_size.le(int(sparse_max)), "sparse", "warm"))
    return cohort.sort_values("user_id", kind="stable").reset_index(drop=True)
