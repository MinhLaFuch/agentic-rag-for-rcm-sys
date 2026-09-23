

from __future__ import annotations

import pandas as pd
from .leakage_error import LeakageError


def duplicate_check(
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
