import pandas as pd
import pytest

from package.data.train import (
    get_user_history,
    leave_one_out_split,
    split_leave_one_out_seq,
    user_history,
)


@pytest.fixture
def synthetic_interactions():
    # rows deliberately unsorted; chronological per user:
    #   u1: i1(1) i2(2) i3(3) i4(4)   u2: i5(1) i6(2)   u3: i7(1)
    return pd.DataFrame(
        {
            "user_id": ["u1", "u2", "u1", "u3", "u1", "u2", "u1"],
            "item_id": ["i3", "i6", "i1", "i7", "i4", "i5", "i2"],
            "timestamp": [3, 2, 1, 1, 4, 1, 2],
        }
    )


# ------------------------------------------------- split_leave_one_out_seq


def test_split_leave_one_out_seq_holds_out_last_interaction_per_user(synthetic_interactions):
    history, held_out = split_leave_one_out_seq(synthetic_interactions)

    assert dict(zip(held_out["user_id"], held_out["item_id"])) == {"u1": "i4", "u2": "i6", "u3": "i7"}
    assert len(history) + len(held_out) == len(synthetic_interactions)


def test_split_leave_one_out_seq_history_is_chronological_remainder(synthetic_interactions):
    history, _ = split_leave_one_out_seq(synthetic_interactions)
    u1 = history[history["user_id"] == "u1"]
    assert list(u1["item_id"]) == ["i1", "i2", "i3"]
    assert "u3" not in set(history["user_id"])  # single interaction -> nothing left over


def test_split_leave_one_out_seq_default_and_custom_columns(synthetic_interactions):
    history, held_out = split_leave_one_out_seq(synthetic_interactions)
    assert list(history.columns) == ["user_id", "item_id", "timestamp"]

    custom, _ = split_leave_one_out_seq(synthetic_interactions, columns=["user_id", "item_id"])
    assert list(custom.columns) == ["user_id", "item_id"]


def test_split_leave_one_out_seq_custom_user_and_time_columns():
    df = pd.DataFrame({"uid": ["a", "a"], "item_id": ["x", "y"], "ts": [2, 1]})
    history, held_out = split_leave_one_out_seq(df, user_col="uid", time_col="ts")
    assert list(held_out["item_id"]) == ["x"]  # ts=2 is the latest
    assert list(history["item_id"]) == ["y"]


def test_split_leave_one_out_seq_resets_index(synthetic_interactions):
    history, held_out = split_leave_one_out_seq(synthetic_interactions)
    assert list(history.index) == list(range(len(history)))
    assert list(held_out.index) == list(range(len(held_out)))


# ----------------------------------------------------- leave_one_out_split


def test_leave_one_out_split_returns_train_valid_test_history(synthetic_interactions):
    train, valid, test, history = leave_one_out_split(synthetic_interactions)

    # u1: history i1,i2,i3 -> test i4 | valid i3 | train i1,i2
    assert dict(zip(test["user_id"], test["item_id"])) == {"u1": "i4", "u2": "i6", "u3": "i7"}
    assert dict(zip(valid["user_id"], valid["item_id"])) == {"u1": "i3", "u2": "i5"}
    assert sorted(train["item_id"]) == ["i1", "i2"]
    assert len(history) == len(train) + len(valid)


def test_leave_one_out_split_column_layout(synthetic_interactions):
    train, valid, test, history = leave_one_out_split(synthetic_interactions)
    assert list(train.columns) == ["user_id", "item_id"]
    assert list(valid.columns) == ["user_id", "item_id"]
    assert list(test.columns) == ["user_id", "item_id", "timestamp"]
    assert list(history.columns) == ["user_id", "item_id", "timestamp"]


def test_leave_one_out_split_short_users_only_reach_the_later_splits(synthetic_interactions):
    train, valid, test, _ = leave_one_out_split(synthetic_interactions)
    assert "u3" in set(test["user_id"]) and "u3" not in set(valid["user_id"])  # 1 interaction: test only
    assert "u2" in set(valid["user_id"]) and "u2" not in set(train["user_id"])  # 2 interactions: no train


def test_leave_one_out_split_has_no_row_in_two_splits(synthetic_interactions):
    train, valid, test, _ = leave_one_out_split(synthetic_interactions)
    pairs = [set(zip(df["user_id"], df["item_id"])) for df in (train, valid, test)]
    assert pairs[0].isdisjoint(pairs[1]) and pairs[0].isdisjoint(pairs[2]) and pairs[1].isdisjoint(pairs[2])
    assert sum(len(p) for p in pairs) == len(synthetic_interactions)


# --------------------------------------------------------- user_history


def test_user_history_lists_items_in_time_order(synthetic_interactions):
    histories = user_history(synthetic_interactions)
    assert histories["u1"] == ["i1", "i2", "i3", "i4"]
    assert histories["u2"] == ["i5", "i6"]
    assert histories["u3"] == ["i7"]


def test_user_history_returns_series_indexed_by_user(synthetic_interactions):
    histories = user_history(synthetic_interactions)
    assert isinstance(histories, pd.Series)
    assert sorted(histories.index) == ["u1", "u2", "u3"]


def test_user_history_falls_back_to_mapped_index_columns():
    df = pd.DataFrame({"user_idx": [0, 0, 1], "item_idx": [5, 4, 9], "timestamp": [2, 1, 1]})
    histories = user_history(df)
    assert histories[0] == [4, 5]
    assert histories[1] == [9]


def test_user_history_without_timestamp_keeps_row_order():
    df = pd.DataFrame({"user_id": ["u1", "u1", "u1"], "item_id": ["c", "a", "b"]})
    assert user_history(df)["u1"] == ["c", "a", "b"]


# ------------------------------------------------------ get_user_history


def test_get_user_history_is_chronological(synthetic_interactions):
    assert get_user_history(synthetic_interactions, "u1") == ["i1", "i2", "i3", "i4"]


def test_get_user_history_unknown_user_is_empty(synthetic_interactions):
    assert get_user_history(synthetic_interactions, "nobody") == []


def test_get_user_history_filters_by_split_column():
    df = pd.DataFrame(
        {
            "user_id": ["u1", "u1", "u1"],
            "item_id": ["a", "b", "c"],
            "timestamp": [1, 2, 3],
            "split": ["train", "train", "test"],
        }
    )
    assert get_user_history(df, "u1", split="train") == ["a", "b"]
    assert get_user_history(df, "u1", split="test") == ["c"]
    assert get_user_history(df, "u1") == ["a", "b", "c"]


def test_get_user_history_split_is_ignored_without_split_column(synthetic_interactions):
    assert get_user_history(synthetic_interactions, "u2", split="train") == ["i5", "i6"]


def test_get_user_history_falls_back_to_mapped_index_columns():
    df = pd.DataFrame({"user_idx": [0, 0, 1], "item_idx": [5, 4, 9], "timestamp": [2, 1, 1]})
    assert get_user_history(df, 0) == [4, 5]
