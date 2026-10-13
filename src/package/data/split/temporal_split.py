"""Chia interaction thành train/validation/test theo hai mốc timestamp (train <= c1 < validation <= c2 < test)."""

from __future__ import annotations

import pandas as pd


def temporal_split(
    df: pd.DataFrame, cutoff_1: int, cutoff_2: int
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = df[df["timestamp"] <= cutoff_1].reset_index(drop=True)
    validation = df[
        (df["timestamp"] > cutoff_1) & (df["timestamp"] <= cutoff_2)
    ].reset_index(drop=True)
    test = df[df["timestamp"] > cutoff_2].reset_index(drop=True)
    return train, validation, test
