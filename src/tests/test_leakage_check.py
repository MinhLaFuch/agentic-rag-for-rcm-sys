import pandas as pd
import pytest

from package.data.leakage import (
    check_profile_snapshot,
    check_split_temporal_order,
    duplicate_check,
)
from package.data.leakage._leakage_error import LeakageError


@pytest.fixture
def valid_split():
    train = pd.DataFrame({"user_id": ["u1", "u2"], "parent_asin": ["i1", "i2"], "timestamp": [100, 200]})
    validation = pd.DataFrame({"user_id": ["u3"], "parent_asin": ["i3"], "timestamp": [300]})
    test = pd.DataFrame({"user_id": ["u4"], "parent_asin": ["i4"], "timestamp": [400]})
    return train, validation, test


def _row(user, item, ts):
    return pd.DataFrame({"user_id": [user], "parent_asin": [item], "timestamp": [ts]})


# ---------------------------------------------------------- LeakageError


def test_leakage_error_is_a_runtime_error():
    assert issubclass(LeakageError, RuntimeError)


# ------------------------------------------- check_split_temporal_order


def test_check_split_temporal_order_passes_on_valid_split(valid_split):
    train, validation, test = valid_split
    check_split_temporal_order(train, validation, test)  # must not raise


def test_check_split_temporal_order_allows_equal_boundary_timestamps(valid_split):
    train, validation, test = valid_split
    validation = pd.concat([validation, _row("u5", "i5", 200)], ignore_index=True)  # == train max
    check_split_temporal_order(train, validation, test)


def test_check_split_temporal_order_DETECTS_leakage_train_into_future(valid_split):
    """
    The most important test of this module: deliberately create leakage (a train row with a
    timestamp AFTER the validation minimum) and verify it really raises LeakageError.
    """
    train, validation, test = valid_split
    leaked_train = pd.concat([train, _row("u_leak", "i_leak", 350)], ignore_index=True)

    with pytest.raises(LeakageError, match="Temporal leakage"):
        check_split_temporal_order(leaked_train, validation, test)


def test_check_split_temporal_order_DETECTS_leakage_validation_into_test(valid_split):
    train, validation, test = valid_split
    leaked_validation = pd.concat([validation, _row("u_leak", "i_leak", 450)], ignore_index=True)

    with pytest.raises(LeakageError, match="Temporal leakage"):
        check_split_temporal_order(train, leaked_validation, test)


def test_check_split_temporal_order_error_message_names_the_timestamps(valid_split):
    train, validation, test = valid_split
    leaked_train = pd.concat([train, _row("u_leak", "i_leak", 350)], ignore_index=True)

    with pytest.raises(LeakageError) as excinfo:
        check_split_temporal_order(leaked_train, validation, test)
    assert "350" in str(excinfo.value) and "300" in str(excinfo.value)


@pytest.mark.parametrize("empty", ["train", "validation", "test"])
def test_check_split_temporal_order_raises_on_empty_split(valid_split, empty):
    frames = dict(zip(["train", "validation", "test"], valid_split))
    frames[empty] = pd.DataFrame(columns=frames[empty].columns)
    with pytest.raises(ValueError, match="empty"):
        check_split_temporal_order(**frames)


# ----------------------------------------------- check_profile_snapshot


def test_check_profile_snapshot_passes_when_no_future_data():
    interactions = pd.DataFrame({"timestamp": [100, 200, 300]})
    check_profile_snapshot(as_of_timestamp=300, source_interactions=interactions)  # == t is allowed


def test_check_profile_snapshot_DETECTS_future_leakage():
    """Profile at t=200 built from data that contains a row at t=250 (the future) -> must raise."""
    interactions = pd.DataFrame({"timestamp": [100, 200, 250]})
    with pytest.raises(LeakageError, match="Profile snapshot leakage"):
        check_profile_snapshot(as_of_timestamp=200, source_interactions=interactions)


def test_check_profile_snapshot_reports_count_and_max_future_timestamp():
    interactions = pd.DataFrame({"timestamp": [100, 250, 900]})
    with pytest.raises(LeakageError) as excinfo:
        check_profile_snapshot(as_of_timestamp=200, source_interactions=interactions)
    assert "2 interaction(s)" in str(excinfo.value)
    assert "900" in str(excinfo.value)


def test_check_profile_snapshot_empty_source_passes():
    check_profile_snapshot(as_of_timestamp=1, source_interactions=pd.DataFrame({"timestamp": []}))


# ------------------------------------------------------- duplicate_check


def test_duplicate_check_passes_on_disjoint_data(valid_split):
    duplicate_check(*valid_split)


def test_duplicate_check_DETECTS_overlap(valid_split):
    train, validation, test = valid_split
    dup_row = _row("u_dup", "i_dup", 999)
    train_with_dup = pd.concat([train, dup_row], ignore_index=True)
    test_with_dup = pd.concat([test, dup_row], ignore_index=True)

    with pytest.raises(LeakageError, match="Duplicate rows found"):
        duplicate_check(train_with_dup, validation, test_with_dup)


@pytest.mark.parametrize(
    "target, expected",
    [
        ("train_val", "train∩val=1, train∩test=0, val∩test=0"),
        ("train_test", "train∩val=0, train∩test=1, val∩test=0"),
        ("val_test", "train∩val=0, train∩test=0, val∩test=1"),
    ],
)
def test_duplicate_check_reports_which_pair_overlaps(valid_split, target, expected):
    train, validation, test = valid_split
    dup_row = _row("u_dup", "i_dup", 999)
    if target == "train_val":
        train, validation = (pd.concat([f, dup_row], ignore_index=True) for f in (train, validation))
    elif target == "train_test":
        train, test = (pd.concat([f, dup_row], ignore_index=True) for f in (train, test))
    else:
        validation, test = (pd.concat([f, dup_row], ignore_index=True) for f in (validation, test))

    with pytest.raises(LeakageError, match=expected):
        duplicate_check(train, validation, test)


def test_duplicate_check_key_columns_are_configurable(valid_split):
    train, validation, test = valid_split
    train = pd.concat([train, _row("shared_user", "i9", 1)], ignore_index=True)
    test = pd.concat([test, _row("shared_user", "i8", 2)], ignore_index=True)

    duplicate_check(train, validation, test)  # different (user, item, ts) -> fine
    with pytest.raises(LeakageError):
        duplicate_check(train, validation, test, key_columns=["user_id"])  # same user -> overlap



