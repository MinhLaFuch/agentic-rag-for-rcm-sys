

from __future__ import annotations

import pandas as pd


class LeakageError(RuntimeError):
    """Raised khi phát hiện data leakage theo thời gian."""


def check_split_temporal_order(
    train: pd.DataFrame, validation: pd.DataFrame, test: pd.DataFrame
) -> None:
    """
    Verify: max(train.timestamp) <= min(validation.timestamp)
        và  max(validation.timestamp) <= min(test.timestamp)

    Raise LeakageError với thông tin cụ thể (không chỉ True/False) nếu
    vi phạm, để dễ debug.
    """
    if len(train) == 0 or len(validation) == 0 or len(test) == 0:
        raise ValueError(
            "One of train/validation/test is empty — cannot verify temporal "
            "order meaningfully. Check split ratios or input data size."
        )

    train_max = train["timestamp"].max()
    val_min = validation["timestamp"].min()
    val_max = validation["timestamp"].max()
    test_min = test["timestamp"].min()

    if train_max > val_min:
        raise LeakageError(
            f"Temporal leakage: train max timestamp ({train_max}) > "
            f"validation min timestamp ({val_min})"
        )
    if val_max > test_min:
        raise LeakageError(
            f"Temporal leakage: validation max timestamp ({val_max}) > "
            f"test min timestamp ({test_min})"
        )


def check_profile_snapshot(
    as_of_timestamp: int, source_interactions: pd.DataFrame
) -> None:
    
    future_rows = source_interactions[
        source_interactions["timestamp"] > as_of_timestamp
    ]
    if len(future_rows) > 0:
        raise LeakageError(
            f"Profile snapshot leakage at t={as_of_timestamp}: "
            f"{len(future_rows)} interaction(s) with timestamp in the future "
            f"(max found: {future_rows['timestamp'].max()})"
        )


def check_no_duplicate_across_splits(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    test: pd.DataFrame,
    key_columns: list[str] | None = None,
) -> None:
    """
    Verify không có row (theo key_columns) xuất hiện ở nhiều hơn 1 split
    — một dạng leakage khác nếu splitting logic bị lỗi và duplicate một
    interaction vào cả train và test.
    """
    keys = key_columns or ["user_id", "parent_asin", "timestamp"]

    train_keys = set(map(tuple, train[keys].values))
    val_keys = set(map(tuple, validation[keys].values))
    test_keys = set(map(tuple, test[keys].values))

    overlap_train_val = train_keys & val_keys
    overlap_train_test = train_keys & test_keys
    overlap_val_test = val_keys & test_keys

    if overlap_train_val or overlap_train_test or overlap_val_test:
        raise LeakageError(
            "Duplicate rows found across splits: "
            f"train∩val={len(overlap_train_val)}, "
            f"train∩test={len(overlap_train_test)}, "
            f"val∩test={len(overlap_val_test)}"
        )
