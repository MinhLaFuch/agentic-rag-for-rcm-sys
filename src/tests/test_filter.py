import pandas as pd
import pytest

from package.data.filter import kcore_filter, low_rating_filter


@pytest.fixture
def synthetic_cascade():
    """With k=2 the filter needs several rounds: u3 only survives the first user pass.

    i3 is seen once (by u3) -> removed -> u3 drops to 1 interaction -> removed next round.
    Final core: {u1, u2} x {i1, i2}.
    """
    return pd.DataFrame(
        {
            "user_id": ["u1", "u1", "u2", "u2", "u3", "u3"],
            "parent_asin": ["i1", "i2", "i1", "i2", "i1", "i3"],
        }
    )


@pytest.fixture
def synthetic_ratings():
    return pd.DataFrame({"user_id": list("abcd"), "rating": [1.0, 2.9, 3.0, 5.0]})


# ------------------------------------------------------------ kcore_filter


def test_kcore_filter_cascades_until_stable(synthetic_cascade):
    result = kcore_filter(synthetic_cascade, user_k=2)
    assert set(result["user_id"]) == {"u1", "u2"}
    assert set(result["parent_asin"]) == {"i1", "i2"}
    assert len(result) == 4


def test_kcore_filter_result_satisfies_thresholds(synthetic_cascade):
    result = kcore_filter(synthetic_cascade, user_k=2, item_k=2)
    assert (result["user_id"].value_counts() >= 2).all()
    assert (result["parent_asin"].value_counts() >= 2).all()


def test_kcore_filter_max_iter_stops_early(synthetic_cascade):
    # one round removes i3 but has not yet propagated to u3
    result = kcore_filter(synthetic_cascade, user_k=2, max_iter=1)
    assert "u3" in set(result["user_id"])
    assert len(result) == 5


def test_kcore_filter_item_k_defaults_to_user_k():
    # 3 users x 3 items, plus i4 seen only twice
    grid = [(u, i) for u in ("u1", "u2", "u3") for i in ("i1", "i2", "i3")]
    df = pd.DataFrame(grid + [("u1", "i4"), ("u2", "i4")], columns=["user_id", "parent_asin"])

    assert len(kcore_filter(df, user_k=3)) == 9  # item_k=3 by default -> i4 (2 visits) is dropped
    assert len(kcore_filter(df, user_k=3, item_k=1)) == 11  # explicit item_k keeps i4
    assert len(kcore_filter(df, user_k=3, item_k=4)) == 0  # stricter item_k removes everything


def test_kcore_filter_user_k_and_item_k_are_independent():
    df = pd.DataFrame(
        {
            "user_id": ["u1", "u1", "u1", "u2"],
            "parent_asin": ["i1", "i2", "i3", "i1"],
        }
    )
    # users need >=2 interactions (drops u2); items need >=1 (keeps everything left)
    result = kcore_filter(df, user_k=2, item_k=1)
    assert set(result["user_id"]) == {"u1"}
    assert set(result["parent_asin"]) == {"i1", "i2", "i3"}


def test_kcore_filter_returns_empty_when_threshold_too_high(synthetic_cascade):
    assert kcore_filter(synthetic_cascade, user_k=10).empty


def test_kcore_filter_already_satisfied_input_is_unchanged():
    df = pd.DataFrame({"user_id": ["u1", "u1", "u2", "u2"], "parent_asin": ["i1", "i2", "i1", "i2"]})
    pd.testing.assert_frame_equal(kcore_filter(df, user_k=2), df)


def test_kcore_filter_does_not_mutate_input_and_resets_index(synthetic_cascade):
    snapshot = synthetic_cascade.copy()
    result = kcore_filter(synthetic_cascade, user_k=2)
    pd.testing.assert_frame_equal(synthetic_cascade, snapshot)
    assert list(result.index) == list(range(len(result)))


# -------------------------------------------------------- low_rating_filter


def test_low_rating_filter_default_threshold_is_inclusive(synthetic_ratings):
    result = low_rating_filter(synthetic_ratings)
    assert list(result["user_id"]) == ["c", "d"]  # 3.0 kept, 2.9 dropped


def test_low_rating_filter_custom_threshold(synthetic_ratings):
    assert list(low_rating_filter(synthetic_ratings, rating_threshold=5.0)["user_id"]) == ["d"]
    assert len(low_rating_filter(synthetic_ratings, rating_threshold=1.0)) == 4


def test_low_rating_filter_resets_index(synthetic_ratings):
    result = low_rating_filter(synthetic_ratings)
    assert list(result.index) == [0, 1]


def test_low_rating_filter_can_remove_everything(synthetic_ratings):
    assert low_rating_filter(synthetic_ratings, rating_threshold=6.0).empty
