"""Giao thức fit/target dùng chung cho mọi script đánh giá."""

from __future__ import annotations

import pandas as pd


def select_fit_target(
    train: pd.DataFrame, validation: pd.DataFrame, test: pd.DataFrame, eval_on: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    validation: fit = train, target = validation (dùng để chọn cấu hình).
    test:       fit = train + validation, target = test (chỉ chạy khi chốt kết quả cuối).
    """
    if eval_on == "validation":
        return train, validation
    if eval_on == "test":
        return pd.concat([train, validation], ignore_index=True), test
    raise ValueError(f"eval_on must be 'validation' or 'test', got {eval_on!r}")
