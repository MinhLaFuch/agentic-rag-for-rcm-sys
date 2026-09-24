import pandas as pd
import pytest

from package.data.clean import clean_interactions, remove_duplicate_interaction


@pytest.fixture
def synthetic_interactions():
    return pd.DataFrame(
        [
            ("u1", "i1", 5.0, 100, "t1"),
            ("u1", "i1", 5.0, 100, "t1_dup"),  # same (user, item, timestamp) -> duplicate key
            ("u2", "i2", None, 200, "t2"),  # missing rating
            ("u3", "i1", 3.0, 300, "t3"),
        ],
        columns=["user_id", "parent_asin", "rating", "timestamp", "title"],
    )


# ------------------------------------------------------ clean_interactions


def test_clean_interactions_drops_missing_and_duplicates(synthetic_interactions):
    cleaned, report = clean_interactions(synthetic_interactions)

    assert report == {
        "num_input": 4,
        "num_dropped_missing_required_fields": 1,  # u2 missing rating
        "num_dropped_duplicates": 1,  # duplicate (u1, i1, 100)
        "num_output": 2,
    }
    assert len(cleaned) == 2


def test_clean_interactions_keeps_first_duplicate(synthetic_interactions):
    cleaned, _ = clean_interactions(synthetic_interactions)
    assert cleaned.loc[cleaned["user_id"] == "u1", "title"].item() == "t1"


def test_clean_interactions_resets_index(synthetic_interactions):
    cleaned, _ = clean_interactions(synthetic_interactions)
    assert list(cleaned.index) == [0, 1]


def test_clean_interactions_does_not_mutate_input(synthetic_interactions):
    snapshot = synthetic_interactions.copy()
    clean_interactions(synthetic_interactions)
    pd.testing.assert_frame_equal(synthetic_interactions, snapshot)


@pytest.mark.parametrize("column", ["user_id", "parent_asin", "rating", "timestamp"])
def test_clean_interactions_drops_nan_in_every_required_column(column):
    df = pd.DataFrame(
        {"user_id": ["u1", "u2"], "parent_asin": ["i1", "i2"], "rating": [5.0, 4.0], "timestamp": [1, 2]}
    )
    df.loc[1, column] = None
    cleaned, report = clean_interactions(df)
    assert len(cleaned) == 1
    assert report["num_dropped_missing_required_fields"] == 1


def test_clean_interactions_same_key_different_rating_is_still_duplicate():
    df = pd.DataFrame(
        {"user_id": ["u1", "u1"], "parent_asin": ["i1", "i1"], "rating": [5.0, 1.0], "timestamp": [1, 1]}
    )
    cleaned, report = clean_interactions(df)
    assert report["num_dropped_duplicates"] == 1
    assert cleaned["rating"].item() == 5.0


def test_clean_interactions_clean_input_is_unchanged():
    df = pd.DataFrame(
        {"user_id": ["u1", "u2"], "parent_asin": ["i1", "i2"], "rating": [5.0, 4.0], "timestamp": [1, 2]}
    )
    cleaned, report = clean_interactions(df)
    pd.testing.assert_frame_equal(cleaned, df)
    assert report["num_dropped_missing_required_fields"] == 0
    assert report["num_dropped_duplicates"] == 0


def test_clean_interactions_raises_on_missing_required_columns():
    bad_df = pd.DataFrame({"user_id": ["u1"], "parent_asin": ["i1"]})
    with pytest.raises(ValueError, match="missing required columns"):
        clean_interactions(bad_df)


# ------------------------------------------- remove_duplicate_interaction


def test_remove_duplicate_interaction_keeps_first_per_user_item_pair():
    df = pd.DataFrame(
        {
            "user_id": ["u1", "u1", "u1", "u2"],
            "item_id": ["i1", "i1", "i2", "i1"],
            "timestamp": [30, 10, 20, 5],  # earliest u1/i1 interaction is t=10
        }
    )
    result = remove_duplicate_interaction(df)

    assert len(result) == 3
    kept = result[(result["user_id"] == "u1") & (result["item_id"] == "i1")]
    assert kept["timestamp"].item() == 10


def test_remove_duplicate_interaction_sorts_by_user_then_time_and_resets_index():
    df = pd.DataFrame(
        {"user_id": ["u2", "u1", "u1"], "item_id": ["i1", "i2", "i1"], "timestamp": [1, 20, 10]}
    )
    result = remove_duplicate_interaction(df)

    assert list(result["user_id"]) == ["u1", "u1", "u2"]
    assert list(result["timestamp"]) == [10, 20, 1]
    assert list(result.index) == [0, 1, 2]


def test_remove_duplicate_interaction_does_not_mutate_input():
    df = pd.DataFrame({"user_id": ["u1", "u1"], "item_id": ["i1", "i1"], "timestamp": [2, 1]})
    snapshot = df.copy()
    remove_duplicate_interaction(df)
    pd.testing.assert_frame_equal(df, snapshot)


def test_remove_duplicate_interaction_uses_item_id_not_parent_asin():
    # this step runs after load_reviews_and_metadata renamed parent_asin -> item_id
    df = pd.DataFrame({"user_id": ["u1"], "parent_asin": ["i1"], "timestamp": [1]})
    with pytest.raises(KeyError):
        remove_duplicate_interaction(df)
