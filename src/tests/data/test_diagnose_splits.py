"""Test cho diagnose_splits - chẩn đoán splits."""

import pandas as pd
import pytest

from package.data.eda import diagnose_splits


def test_diagnose_splits_basic():
    """Test chẩn đoán với dữ liệu cơ bản."""
    train = pd.DataFrame({
        "user_idx": [0, 0, 1, 1, 2],
        "item_idx": [0, 1, 0, 2, 3],
        "timestamp": [1, 2, 3, 4, 5],
        "domain": ["Electronics", "Electronics", "Toys", "Toys", "Video_Games"],
    })
    validation = pd.DataFrame({
        "user_idx": [0, 1],
        "item_idx": [2, 3],
        "timestamp": [6, 7],
        "domain": ["Toys", "Video_Games"],
    })
    test = pd.DataFrame({
        "user_idx": [0, 2],
        "item_idx": [4, 0],
        "timestamp": [8, 9],
        "domain": ["Electronics", "Electronics"],
    })

    diagnosis = diagnose_splits(train, validation, test)

    # Kiểm tra số lượng cơ bản
    assert diagnosis.train_rows == 5
    assert diagnosis.val_rows == 2
    assert diagnosis.test_rows == 2
    assert diagnosis.train_users == 3
    assert diagnosis.val_users == 2
    assert diagnosis.test_users == 2
    assert diagnosis.train_items == 4
    assert diagnosis.val_items == 2
    assert diagnosis.test_items == 2

    # Kiểm tra timestamp
    assert diagnosis.train_timestamp_min == 1
    assert diagnosis.train_timestamp_max == 5
    assert diagnosis.val_timestamp_min == 6
    assert diagnosis.val_timestamp_max == 7
    assert diagnosis.test_timestamp_min == 8
    assert diagnosis.test_timestamp_max == 9

    # Kiểm tra target item coverage
    # Val items: {2, 3}, train items: {0, 1, 2, 3} → 100% val items in train
    assert diagnosis.val_items_in_train_pct == 100.0
    # Test items: {4, 0}, train items: {0, 1, 2, 3} → 50% test items in train (item 0)
    assert diagnosis.test_items_in_train_pct == 50.0

    # Kiểm tra user history coverage
    # Val users: {0, 1}, train users: {0, 1, 2} → 100% val users in train
    assert diagnosis.val_users_with_train_history_pct == 100.0
    # Test users: {0, 2}, train users: {0, 1, 2} → 100% test users in train
    assert diagnosis.test_users_with_train_history_pct == 100.0

    # Kiểm tra repeat pairs
    # Train pairs: {(0,0), (0,1), (1,0), (1,2), (2,3)}
    # Val pairs: {(0,2), (1,3)} → không trùng → 0%
    assert diagnosis.val_repeat_pairs_pct == 0.0
    # Test pairs: {(0,4), (2,0)} → (2,0) không trong train → 0%
    assert diagnosis.test_repeat_pairs_pct == 0.0

    # Kiểm tra reachable (item in train AND pair not in history)
    # Val: (0,2) item 2 in train, (0,2) not in train history → reachable
    #      (1,3) item 3 in train, (1,3) not in train history → reachable
    # → 100%
    assert diagnosis.val_reachable_pct == 100.0
    # Test: (0,4) item 4 NOT in train → not reachable
    #       (2,0) item 0 in train, (2,0) not in train history → reachable
    # → 50%
    assert diagnosis.test_reachable_pct == 50.0


def test_diagnose_splits_with_repeat_pairs():
    """Test phát hiện repeat pairs (leakage)."""
    train = pd.DataFrame({
        "user_idx": [0, 0, 1],
        "item_idx": [0, 1, 2],
        "timestamp": [1, 2, 3],
    })
    validation = pd.DataFrame({
        "user_idx": [0, 1],
        "item_idx": [0, 2],  # (0,0) repeat from train, (1,2) repeat from train
        "timestamp": [4, 5],
    })
    test = pd.DataFrame({
        "user_idx": [0, 1],
        "item_idx": [1, 0],  # (0,1) repeat from train, (1,0) not in train
        "timestamp": [6, 7],
    })

    diagnosis = diagnose_splits(train, validation, test)

    # Val: 2/2 pairs repeat → 100%
    assert diagnosis.val_repeat_pairs_pct == 100.0
    # Test: 1/2 pairs repeat → 50%
    assert diagnosis.test_repeat_pairs_pct == 50.0

    # Reachable:
    # Val: (0,0) item in train but pair in history → not reachable
    #      (1,2) item in train but pair in history → not reachable
    # → 0%
    assert diagnosis.val_reachable_pct == 0.0
    # Test: (0,1) item in train but pair in history → not reachable
    #       (1,0) item 0 IS in train, (1,0) not in train history → reachable
    # → 50%
    assert diagnosis.test_reachable_pct == 50.0


def test_diagnose_splits_items_only_in_test():
    """Test khi item chỉ xuất hiện ở test (cold-start)."""
    train = pd.DataFrame({
        "user_idx": [0, 1],
        "item_idx": [0, 1],
        "timestamp": [1, 2],
    })
    validation = pd.DataFrame({
        "user_idx": [0],
        "item_idx": [2],  # item 2 chỉ ở val
        "timestamp": [3],
    })
    test = pd.DataFrame({
        "user_idx": [1],
        "item_idx": [3],  # item 3 chỉ ở test
        "timestamp": [4],
    })

    diagnosis = diagnose_splits(train, validation, test)

    # Val items: {2}, train items: {0, 1} → 0% val items in train
    assert diagnosis.val_items_in_train_pct == 0.0
    # Test items: {3}, train items: {0, 1} → 0% test items in train
    assert diagnosis.test_items_in_train_pct == 0.0

    # Reachable: cả hai item đều không trong train → 0%
    assert diagnosis.val_reachable_pct == 0.0
    assert diagnosis.test_reachable_pct == 0.0


def test_diagnose_splits_empty_split():
    """Test khi một split rỗng không bị lỗi chia cho 0."""
    train = pd.DataFrame({
        "user_idx": [0, 1],
        "item_idx": [0, 1],
        "timestamp": [1, 2],
    })
    validation = pd.DataFrame({
        "user_idx": [],
        "item_idx": [],
        "timestamp": [],
    })
    test = pd.DataFrame({
        "user_idx": [0],
        "item_idx": [2],
        "timestamp": [3],
    })

    diagnosis = diagnose_splits(train, validation, test)

    assert diagnosis.val_rows == 0
    assert diagnosis.val_users == 0
    assert diagnosis.val_items == 0
    assert diagnosis.val_items_in_train_pct == 0.0  # Không chia cho 0
    assert diagnosis.val_repeat_pairs_pct == 0.0
    assert diagnosis.val_reachable_pct == 0.0


def test_diagnose_splits_multi_domain():
    """Test tính % user đa-domain."""
    train = pd.DataFrame({
        "user_idx": [0, 0, 1, 2, 2],
        "item_idx": [0, 1, 2, 3, 4],
        "timestamp": [1, 2, 3, 4, 5],
        "domain": ["Electronics", "Toys", "Toys", "Electronics", "Video_Games"],
    })
    # User 0: Electronics + Toys (multi-domain)
    # User 1: Toys (single-domain)
    # User 2: Electronics + Video_Games (multi-domain)
    # → 2/3 users multi-domain → 66.67%

    diagnosis = diagnose_splits(train, train, train)

    assert diagnosis.train_multi_domain_users_pct == pytest.approx(66.67, rel=0.01)


def test_diagnose_splits_without_domain_column():
    """Test khi không có cột domain."""
    train = pd.DataFrame({
        "user_idx": [0, 1],
        "item_idx": [0, 1],
        "timestamp": [1, 2],
    })
    validation = pd.DataFrame({
        "user_idx": [0],
        "item_idx": [2],
        "timestamp": [3],
    })
    test = pd.DataFrame({
        "user_idx": [1],
        "item_idx": [3],
        "timestamp": [4],
    })

    diagnosis = diagnose_splits(train, validation, test)

    # Không có domain → % multi-domain = 0
    assert diagnosis.train_multi_domain_users_pct == 0.0
    assert diagnosis.val_multi_domain_users_pct == 0.0
    assert diagnosis.test_multi_domain_users_pct == 0.0
    # Domain ratios rỗng
    assert diagnosis.train_domain_ratios == {}
    assert diagnosis.val_domain_ratios == {}
    assert diagnosis.test_domain_ratios == {}


def test_diagnose_splits_missing_required_columns():
    """Test lỗi khi thiếu cột bắt buộc."""
    train = pd.DataFrame({
        "user_idx": [0, 1],
        "timestamp": [1, 2],
    })
    validation = pd.DataFrame({
        "user_idx": [0],
        "item_idx": [0],
    })

    with pytest.raises(ValueError, match="train missing columns"):
        diagnose_splits(train, validation, validation)


def test_runtime_fit_zero_history_and_unique_pairs():
    train = pd.DataFrame({"user_idx": [0, 0], "item_idx": [0, 0]})
    val = pd.DataFrame({"user_idx": [0, 1, 1], "item_idx": [0, 2, 2], "domain": ["A", "B", "B"]})
    test = pd.DataFrame({"user_idx": [2, 1], "item_idx": [2, 2], "domain": ["B", "B"]})
    d = diagnose_splits(train, val, test)
    assert d.val_repeat_pairs_pct == 50  # 1/2 pairs, NOT 1/3 rows
    assert d.val_history_len_stats == {"min": 0., "median": .5, "p90": .9}
    assert d.test_reachable_pct == 50  # item 2 is in validation, not train
    assert d.test_items_in_train_pct == 0  # explicit train-only legacy field
    assert d.fit_diagnostics["test"]["cold_user_pct"] == 50
    assert d.fit_diagnostics["test"]["history_unique_items_including_zero"]["median"] == .5
    assert d.domain_diagnostics["validation"]["B"]["cold_user_pct"] == 100


def test_all_empty_diagnostics():
    empty = pd.DataFrame(columns=["user_idx", "item_idx"])
    d = diagnose_splits(empty, empty, empty)
    assert d.test_reachable_pct == 0
    assert d.fit_diagnostics["validation"]["catalog_eligible_macro_recall_at_10_upper_bound"] is None


@pytest.mark.parametrize("seed", range(10))
def test_numeric_diagnostic_matches_independent_set_reference(seed):
    import numpy as np
    rng = np.random.default_rng(seed)
    frames = [pd.DataFrame({"user_idx": rng.integers(0, 12, n), "item_idx": rng.integers(0, 15, n)}) for n in (50, 30, 25)]
    d = diagnose_splits(*frames)
    sets = [set(zip(f.user_idx, f.item_idx)) for f in frames]
    for name, target, fit in (("validation", sets[1], sets[0]), ("test", sets[2], sets[0] | sets[1])):
        items = {i for _, i in fit}
        users = {u for u, _ in target}
        expected = sum(i in items and (u,i) not in fit for u,i in target) / len(target) * 100
        assert d.fit_diagnostics[name]["novel_item_warm_unique_pair_pct"] == pytest.approx(expected)
        ceiling = sum(min(10, sum(v == u and i in items and (v,i) not in fit for v,i in target)) / sum(v == u for v,_ in target) for u in users) / len(users)
        assert d.fit_diagnostics[name]["catalog_eligible_macro_recall_at_10_upper_bound"] == pytest.approx(ceiling)
