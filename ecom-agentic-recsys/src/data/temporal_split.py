from __future__ import annotations

import pandas as pd


def compute_temporal_cutoffs(
    df: pd.DataFrame,
    train_ratio: float = 0.8,
    validation_ratio: float = 0.1,
    test_ratio: float = 0.1,
) -> tuple[int, int]:
    """
    Trả về (cutoff_1, cutoff_2) sao cho:
        train      = timestamp <= cutoff_1
        validation = cutoff_1 < timestamp <= cutoff_2
        test       = timestamp > cutoff_2
    """
    total = train_ratio + validation_ratio + test_ratio
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"Ratios must sum to 1.0, got {total}")

    sorted_ts = df["timestamp"].sort_values().reset_index(drop=True)
    n = len(sorted_ts)
    if n == 0:
        raise ValueError("Cannot compute cutoffs on empty DataFrame")

    idx_1 = int(n * train_ratio) - 1
    idx_2 = int(n * (train_ratio + validation_ratio)) - 1

    idx_1 = max(0, min(idx_1, n - 1))
    idx_2 = max(idx_1, min(idx_2, n - 1))

    cutoff_1 = int(sorted_ts.iloc[idx_1])
    cutoff_2 = int(sorted_ts.iloc[idx_2])
    return cutoff_1, cutoff_2


def temporal_split(
    df: pd.DataFrame, cutoff_1: int, cutoff_2: int
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = df[df["timestamp"] <= cutoff_1].reset_index(drop=True)
    validation = df[
        (df["timestamp"] > cutoff_1) & (df["timestamp"] <= cutoff_2)
    ].reset_index(drop=True)
    test = df[df["timestamp"] > cutoff_2].reset_index(drop=True)
    return train, validation, test
