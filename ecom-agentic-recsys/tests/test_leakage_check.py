import pandas as pd
import pytest

from src.data.leakage_check import (
    LeakageError,
    check_no_duplicate_across_splits,
    check_profile_snapshot,
    check_split_temporal_order,
)


@pytest.fixture
def valid_split():
    train = pd.DataFrame({"user_id": ["u1", "u2"], "parent_asin": ["i1", "i2"], "timestamp": [100, 200]})
    validation = pd.DataFrame({"user_id": ["u3"], "parent_asin": ["i3"], "timestamp": [300]})
    test = pd.DataFrame({"user_id": ["u4"], "parent_asin": ["i4"], "timestamp": [400]})
    return train, validation, test


def test_check_split_temporal_order_passes_on_valid_split(valid_split):
    train, validation, test = valid_split
    # Không raise -> hợp lệ
    check_split_temporal_order(train, validation, test)


def test_check_split_temporal_order_DETECTS_leakage_train_into_future(valid_split):
    """
    Test QUAN TRỌNG NHẤT của module này: cố tình tạo leakage (chèn 1 dòng
    train có timestamp NẰM SAU validation) và verify hàm THỰC SỰ raise
    LeakageError, không chỉ pass suông như test phía trên.
    """
    train, validation, test = valid_split
    # Chèn 1 row "từ tương lai" vào train (timestamp 350 > validation max 300)
    leaked_train = pd.concat(
        [train, pd.DataFrame({"user_id": ["u_leak"], "parent_asin": ["i_leak"], "timestamp": [350]})],
        ignore_index=True,
    )

    with pytest.raises(LeakageError, match="Temporal leakage"):
        check_split_temporal_order(leaked_train, validation, test)


def test_check_split_temporal_order_DETECTS_leakage_validation_into_test(valid_split):
    train, validation, test = valid_split
    leaked_validation = pd.concat(
        [validation, pd.DataFrame({"user_id": ["u_leak"], "parent_asin": ["i_leak"], "timestamp": [450]})],
        ignore_index=True,
    )
    with pytest.raises(LeakageError, match="Temporal leakage"):
        check_split_temporal_order(train, leaked_validation, test)


def test_check_split_temporal_order_raises_on_empty_split(valid_split):
    train, validation, test = valid_split
    with pytest.raises(ValueError):
        check_split_temporal_order(train, pd.DataFrame(columns=validation.columns), test)


def test_check_profile_snapshot_passes_when_no_future_data():
    interactions = pd.DataFrame({"timestamp": [100, 200, 300]})
    # Không raise
    check_profile_snapshot(as_of_timestamp=300, source_interactions=interactions)


def test_check_profile_snapshot_DETECTS_future_leakage():
    """
    Test quan trọng: profile tại t=200 nhưng source data có 1 dòng
    timestamp=250 (tương lai so với t) -> PHẢI raise.
    """
    interactions = pd.DataFrame({"timestamp": [100, 200, 250]})
    with pytest.raises(LeakageError, match="Profile snapshot leakage"):
        check_profile_snapshot(as_of_timestamp=200, source_interactions=interactions)


def test_check_no_duplicate_across_splits_passes_on_disjoint_data(valid_split):
    train, validation, test = valid_split
    check_no_duplicate_across_splits(train, validation, test)


def test_check_no_duplicate_across_splits_DETECTS_overlap(valid_split):
    train, validation, test = valid_split
    # Chèn row trùng key (user_id, parent_asin, timestamp) vào cả train và test
    dup_row = pd.DataFrame({"user_id": ["u_dup"], "parent_asin": ["i_dup"], "timestamp": [999]})
    train_with_dup = pd.concat([train, dup_row], ignore_index=True)
    test_with_dup = pd.concat([test, dup_row], ignore_index=True)

    with pytest.raises(LeakageError, match="Duplicate rows found"):
        check_no_duplicate_across_splits(train_with_dup, validation, test_with_dup)
