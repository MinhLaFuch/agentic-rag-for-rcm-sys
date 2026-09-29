"""
Temporal split (mục VI — BẮT BUỘC, không được random split cho
interaction data).

Chiến lược: cắt theo timestamp quantile trên TOÀN BỘ interaction (global
split theo thời gian), đúng nguyên tắc "train < validation < test" nêu
trong spec gốc — không phải leave-one-out per-user (cách đó phổ biến
trong literature sequential rec nhưng dễ vi phạm leakage nếu không cẩn
thận, và spec gốc chỉ định rõ global temporal split).
"""

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
