"""
Tests for the EDA helpers use SYNTHETIC data (not the real Amazon Reviews 2023):
the goal is to verify the calculations, not to report real numbers.
"""

import pandas as pd
import pytest

from package.data.eda import inter_eda, segment_users
from package.data.eda.inter_stat import InteractionStats


@pytest.fixture
def synthetic_interactions() -> pd.DataFrame:
    rows = [
        # u1: 5 interactions (warm)
        ("u1", "i1", 5.0, 100),
        ("u1", "i2", 4.0, 200),
        ("u1", "i1", 3.0, 300),
        ("u1", "i3", 5.0, 400),
        ("u1", "i2", 2.0, 500),
        # u2: 2 interactions (sparse)
        ("u2", "i1", 4.0, 150),
        ("u2", "i3", 5.0, 250),
        # u3: 1 interaction
        ("u3", "i2", 3.0, 600),
    ]
    return pd.DataFrame(rows, columns=["user_id", "parent_asin", "rating", "timestamp"])


# ------------------------------------------------------------- inter_eda


def test_inter_eda_basic_counts(synthetic_interactions):
    stats = inter_eda(synthetic_interactions)
    assert isinstance(stats, InteractionStats)
    assert stats.num_users == 3
    assert stats.num_items == 3
    assert stats.num_interactions == 8
    assert stats.timestamp_min == 100
    assert stats.timestamp_max == 600


def test_inter_eda_sparsity(synthetic_interactions):
    stats = inter_eda(synthetic_interactions)
    assert stats.sparsity == pytest.approx(1 - 8 / (3 * 3))


def test_inter_eda_per_user_distribution(synthetic_interactions):
    # per-user counts are [5, 2, 1]
    stats = inter_eda(synthetic_interactions)
    assert stats.avg_interactions_per_user == pytest.approx(8 / 3)
    assert stats.median_interactions_per_user == pytest.approx(2.0)
    assert stats.p90_interactions_per_user == pytest.approx(4.4)  # 2 + 0.8 * (5 - 2)


def test_inter_eda_timestamps_are_plain_ints(synthetic_interactions):
    stats = inter_eda(synthetic_interactions)
    assert isinstance(stats.timestamp_min, int) and isinstance(stats.timestamp_max, int)


def test_inter_eda_does_not_need_rating_column(synthetic_interactions):
    stats = inter_eda(synthetic_interactions.drop(columns=["rating"]))
    assert stats.num_interactions == 8


@pytest.mark.parametrize("missing", ["user_id", "parent_asin", "timestamp"])
def test_inter_eda_missing_column_raises(synthetic_interactions, missing):
    with pytest.raises(ValueError, match="missing columns"):
        inter_eda(synthetic_interactions.drop(columns=[missing]))


# ---------------------------------------------------------- segment_users


def test_segment_users_assigns_sparse_and_warm(synthetic_interactions):
    segments = segment_users(synthetic_interactions, as_of_timestamp=600, sparse_threshold=2)
    seg_map = dict(zip(segments["user_id"], segments["segment"]))
    assert seg_map["u1"] == "warm"  # 5 interactions > threshold
    assert seg_map["u2"] == "sparse_history"  # 2 == threshold
    assert seg_map["u3"] == "sparse_history"  # 1 <= threshold


def test_segment_users_output_columns_and_counts(synthetic_interactions):
    segments = segment_users(synthetic_interactions, as_of_timestamp=600)
    assert list(segments.columns) == ["user_id", "n_interactions", "segment", "evolving_interest"]
    assert dict(zip(segments["user_id"], segments["n_interactions"])) == {"u1": 5, "u2": 2, "u3": 1}


def test_segment_users_default_threshold_is_three(synthetic_interactions):
    segments = segment_users(synthetic_interactions, as_of_timestamp=600)
    seg_map = dict(zip(segments["user_id"], segments["segment"]))
    assert seg_map["u1"] == "warm"
    assert seg_map["u2"] == "sparse_history"


def test_segment_users_respects_as_of_timestamp(synthetic_interactions):
    # at t=200 u1 only has 2 interactions (t=100, 200)
    segments = segment_users(synthetic_interactions, as_of_timestamp=200, sparse_threshold=2)
    seg_map = dict(zip(segments["user_id"], segments["segment"]))
    assert seg_map["u1"] == "sparse_history"
    assert "u3" not in seg_map  # u3 has no interaction yet at t=200


def test_segment_users_as_of_timestamp_is_inclusive(synthetic_interactions):
    segments = segment_users(synthetic_interactions, as_of_timestamp=100, sparse_threshold=2)
    assert dict(zip(segments["user_id"], segments["n_interactions"])) == {"u1": 1}


def test_segment_users_evolving_interest_is_false_without_category_data(synthetic_interactions):
    # must not be guessed when there is no data for it
    segments = segment_users(synthetic_interactions, as_of_timestamp=600)
    assert not segments["evolving_interest"].any()


def test_segment_users_evolving_category_col_is_still_a_placeholder(synthetic_interactions):
    synthetic_interactions["category"] = "Beauty"
    segments = segment_users(synthetic_interactions, as_of_timestamp=600, evolving_category_col="category")
    assert not segments["evolving_interest"].any()
