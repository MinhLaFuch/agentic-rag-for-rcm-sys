"""Stable fingerprint for the exact interaction pairs used to fit ItemKNN."""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd


def item_knn_data_hash(fit_pairs: pd.DataFrame) -> str:
    """Hash sorted ``user_idx``/``item_idx`` pairs using the cache format's protocol."""
    if not {"user_idx", "item_idx"}.issubset(fit_pairs.columns):
        raise ValueError("fit_pairs must contain user_idx and item_idx columns")
    users = fit_pairs["user_idx"].to_numpy(dtype=np.int64)
    items = fit_pairs["item_idx"].to_numpy(dtype=np.int64)
    for column in ("user_idx", "item_idx"):
        values = fit_pairs[column]
        if values.isna().any() or (values < 0).any() or not np.array_equal(values.to_numpy(), values.to_numpy(dtype=np.int64)):
            raise ValueError("fit indices must be non-negative integers without nulls")
    order = np.lexsort((items, users))
    return hashlib.sha256(np.column_stack((users[order], items[order])).astype("<i8", copy=False).tobytes()).hexdigest()
