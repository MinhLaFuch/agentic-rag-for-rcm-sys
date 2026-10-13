"""
Chẩn đoán splits để hiểu lý do recall@10 ≈ 0.

Pure function, không tự đọc dữ liệu — dễ unit test bằng dữ liệu synthetic.
"""

from __future__ import annotations

import pandas as pd

from ._dataclass import SplitDiagnosis


def diagnose_splits(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    test: pd.DataFrame,
    user2id: dict[str, int] | None = None,
    item2id: dict[str, int] | None = None,
) -> SplitDiagnosis:
    """
    Chẩn đoán splits để hiểu lý do recall@10 ≈ 0.

    Args:
        train: DataFrame với cột user_idx, item_idx, (tùy chọn: timestamp, domain)
        validation: DataFrame với cột user_idx, item_idx, (tùy chọn: timestamp, domain)
        test: DataFrame với cột user_idx, item_idx, (tùy chọn: timestamp, domain)
        user2id: Optional mapping từ user_id gốc sang user_idx (nếu cần tính multi-domain từ id)
        item2id: Optional mapping từ item_id gốc sang item_idx (nếu cần tính multi-domain từ id)

    Returns:
        SplitDiagnosis với các chỉ số chẩn đoán
    """
    # Đảm bảo có các cột cần thiết
    required_cols = {"user_idx", "item_idx"}
    for df, name in [(train, "train"), (validation, "validation"), (test, "test")]:
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"{name} missing columns: {missing}")

    # Số dòng/user/item từng split
    train_rows = len(train)
    val_rows = len(validation)
    test_rows = len(test)

    train_users = train["user_idx"].nunique()
    val_users = validation["user_idx"].nunique()
    test_users = test["user_idx"].nunique()

    train_items = train["item_idx"].nunique()
    val_items = validation["item_idx"].nunique()
    test_items = test["item_idx"].nunique()

    # Timestamp range (nếu có)
    if "timestamp" in train.columns and len(train) > 0:
        train_timestamp_min = int(train["timestamp"].min())
        train_timestamp_max = int(train["timestamp"].max())
    else:
        train_timestamp_min = 0
        train_timestamp_max = 0

    if "timestamp" in validation.columns and len(validation) > 0:
        val_timestamp_min = int(validation["timestamp"].min())
        val_timestamp_max = int(validation["timestamp"].max())
    else:
        val_timestamp_min = 0
        val_timestamp_max = 0

    if "timestamp" in test.columns and len(test) > 0:
        test_timestamp_min = int(test["timestamp"].min())
        test_timestamp_max = int(test["timestamp"].max())
    else:
        test_timestamp_min = 0
        test_timestamp_max = 0

    # Domain distribution (nếu có cột domain)
    if "domain" in train.columns:
        train_domain_counts = train["domain"].value_counts(normalize=True).to_dict()
        val_domain_counts = validation["domain"].value_counts(normalize=True).to_dict()
        test_domain_counts = test["domain"].value_counts(normalize=True).to_dict()
    else:
        train_domain_counts = {}
        val_domain_counts = {}
        test_domain_counts = {}

    # Target item coverage
    train_items_set = set(train["item_idx"])
    val_items_set = set(validation["item_idx"])
    test_items_set = set(test["item_idx"])

    val_items_in_train = len(val_items_set & train_items_set)
    test_items_in_train = len(test_items_set & train_items_set)

    val_items_in_train_pct = (val_items_in_train / len(val_items_set) * 100) if val_items_set else 0.0
    test_items_in_train_pct = (test_items_in_train / len(test_items_set) * 100) if test_items_set else 0.0

    val_rows_with_train_item = validation["item_idx"].isin(train_items_set).sum()
    test_rows_with_train_item = test["item_idx"].isin(train_items_set).sum()

    val_rows_with_train_item_pct = (val_rows_with_train_item / val_rows * 100) if val_rows else 0.0
    test_rows_with_train_item_pct = (test_rows_with_train_item / test_rows * 100) if test_rows else 0.0

    # User history coverage
    train_users_set = set(train["user_idx"])
    val_users_set = set(validation["user_idx"])
    test_users_set = set(test["user_idx"])

    val_users_with_train_history = len(val_users_set & train_users_set)
    test_users_with_train_history = len(test_users_set & train_users_set)

    val_users_with_train_history_pct = (val_users_with_train_history / len(val_users_set) * 100) if val_users_set else 0.0
    test_users_with_train_history_pct = (test_users_with_train_history / len(test_users_set) * 100) if test_users_set else 0.0

    # Phân bố độ dài lịch sử train cho val/test users
    train_history_per_user = train.groupby("user_idx").size()

    val_history_lengths = []
    for user in val_users_set:
        if user in train_history_per_user:
            val_history_lengths.append(train_history_per_user[user])

    test_history_lengths = []
    for user in test_users_set:
        if user in train_history_per_user:
            test_history_lengths.append(train_history_per_user[user])

    if val_history_lengths:
        val_history_len_stats = {
            "min": float(min(val_history_lengths)),
            "median": float(pd.Series(val_history_lengths).median()),
            "p90": float(pd.Series(val_history_lengths).quantile(0.9)),
        }
    else:
        val_history_len_stats = {"min": 0.0, "median": 0.0, "p90": 0.0}

    if test_history_lengths:
        test_history_len_stats = {
            "min": float(min(test_history_lengths)),
            "median": float(pd.Series(test_history_lengths).median()),
            "p90": float(pd.Series(test_history_lengths).quantile(0.9)),
        }
    else:
        test_history_len_stats = {"min": 0.0, "median": 0.0, "p90": 0.0}

    # Repeat pairs (leakage)
    train_pairs = set(zip(train["user_idx"], train["item_idx"]))
    val_pairs = set(zip(validation["user_idx"], validation["item_idx"]))
    test_pairs = set(zip(test["user_idx"], test["item_idx"]))

    val_repeat_pairs = len(val_pairs & train_pairs)
    test_repeat_pairs = len(test_pairs & (train_pairs | val_pairs))

    val_repeat_pairs_pct = (val_repeat_pairs / len(val_pairs) * 100) if val_pairs else 0.0
    test_repeat_pairs_pct = (test_repeat_pairs / len(test_pairs) * 100) if test_pairs else 0.0

    # Theoretical recall ceiling (reachable: item in train AND pair not in history)
    val_reachable = 0
    for user, item in val_pairs:
        if item in train_items_set and (user, item) not in train_pairs:
            val_reachable += 1

    test_reachable = 0
    for user, item in test_pairs:
        if item in train_items_set and (user, item) not in (train_pairs | val_pairs):
            test_reachable += 1

    val_reachable_pct = (val_reachable / len(val_pairs) * 100) if val_pairs else 0.0
    test_reachable_pct = (test_reachable / len(test_pairs) * 100) if test_pairs else 0.0

    # Multi-domain users (nếu có domain column hoặc có thể suy ra từ item_id)
    if "domain" in train.columns:
        train_multi_domain_users_pct = _compute_multi_domain_pct(train)
        val_multi_domain_users_pct = _compute_multi_domain_pct(validation)
        test_multi_domain_users_pct = _compute_multi_domain_pct(test)
    else:
        # Nếu không có domain column, không thể tính
        train_multi_domain_users_pct = 0.0
        val_multi_domain_users_pct = 0.0
        test_multi_domain_users_pct = 0.0

    return SplitDiagnosis(
        train_rows=train_rows,
        val_rows=val_rows,
        test_rows=test_rows,
        train_users=train_users,
        val_users=val_users,
        test_users=test_users,
        train_items=train_items,
        val_items=val_items,
        test_items=test_items,
        train_timestamp_min=train_timestamp_min,
        train_timestamp_max=train_timestamp_max,
        val_timestamp_min=val_timestamp_min,
        val_timestamp_max=val_timestamp_max,
        test_timestamp_min=test_timestamp_min,
        test_timestamp_max=test_timestamp_max,
        train_domain_ratios=train_domain_counts,
        val_domain_ratios=val_domain_counts,
        test_domain_ratios=test_domain_counts,
        val_items_in_train_pct=val_items_in_train_pct,
        test_items_in_train_pct=test_items_in_train_pct,
        val_rows_with_train_item_pct=val_rows_with_train_item_pct,
        test_rows_with_train_item_pct=test_rows_with_train_item_pct,
        val_users_with_train_history_pct=val_users_with_train_history_pct,
        test_users_with_train_history_pct=test_users_with_train_history_pct,
        val_history_len_stats=val_history_len_stats,
        test_history_len_stats=test_history_len_stats,
        val_repeat_pairs_pct=val_repeat_pairs_pct,
        test_repeat_pairs_pct=test_repeat_pairs_pct,
        val_reachable_pct=val_reachable_pct,
        test_reachable_pct=test_reachable_pct,
        train_multi_domain_users_pct=train_multi_domain_users_pct,
        val_multi_domain_users_pct=val_multi_domain_users_pct,
        test_multi_domain_users_pct=test_multi_domain_users_pct,
    )


def _compute_multi_domain_pct(df: pd.DataFrame) -> float:
    """Tính % user có interaction với >1 domain."""
    if "domain" not in df.columns:
        return 0.0

    domains_per_user = df.groupby("user_idx")["domain"].nunique()
    multi_domain_users = (domains_per_user > 1).sum()
    total_users = len(domains_per_user)

    return (multi_domain_users / total_users * 100) if total_users else 0.0
