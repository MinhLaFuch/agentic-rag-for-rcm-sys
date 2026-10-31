"""Verify that a model-fit core contains only interactions from train."""

from __future__ import annotations

import pandas as pd

from ._error import LeakageError


def check_fit_core_subset(train: pd.DataFrame, fit_core: pd.DataFrame) -> None:
    """Raise LeakageError if fit_core has a row/pair absent from chronological train."""
    required = {"user_id", "parent_asin", "timestamp"}
    missing = required - set(train.columns) | required - set(fit_core.columns)
    if missing:
        raise ValueError(f"train/fit_core missing required columns: {sorted(missing)}")
    columns = ["user_id", "parent_asin", "timestamp"]
    train_counts = train.groupby(columns, dropna=False).size()
    core_counts = fit_core.groupby(columns, dropna=False).size()
    aligned = train_counts.reindex(core_counts.index, fill_value=0)
    invalid = core_counts[core_counts > aligned]
    if len(invalid):
        raise LeakageError(f"fit-core contains {len(invalid)} interaction keys/counts absent from train")
