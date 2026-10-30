"""Tests for memory oracle (independent verification of MemoryTool logic)."""

import pandas as pd
import pytest

from package.evaluation.component.benchmarks.memory_oracle import compute_memory_oracle


@pytest.fixture
def meta_df():
    """Metadata DataFrame for oracle."""
    return pd.DataFrame({
        "parent_asin": ["vg_a", "vg_b", "vg_c", "vg_d", "vg_e"],
        "domain": ["Video_Games"] * 5,
        "title": ["Pricey Game", "Cheap Game", "Mid Game", "Pricey Game 2", "Cheap Game 2"],
        "store": ["StoreA", "StoreB", "StoreC", "StoreA", "StoreB"],
        "price": [300.0, 1.0, 150.0, 250.0, 2.0],
        "average_rating": [4.5, 3.5, 4.0, 4.2, 3.8],
        "rating_number": [100, 50, 75, 80, 60],
        "main_category": ["Pricey", "Cheap", "Mid", "Pricey", "Cheap"],
        "categories": [
            ["Pricey", "Action"],
            ["Cheap", "Puzzle"],
            ["Mid", "RPG"],
            ["Pricey", "Adventure"],
            ["Cheap", "Strategy"],
        ],
    })


def test_oracle_basic_love_hate(meta_df):
    """Test oracle computes love/hate correctly with mixed ratings."""
    interactions = pd.DataFrame({
        "user_id": ["u_mix"] * 5,
        "item_id": ["Video_Games::vg_a", "Video_Games::vg_b", "Video_Games::vg_c",
                   "Video_Games::vg_d", "Video_Games::vg_e"],
        "user_idx": [0] * 5,
        "item_idx": [0, 1, 2, 3, 4],
        "rating": [5, 4, 3, 2, 1],
        "timestamp": [0, 1, 2, 3, 4],
    })
    user2id = {"u_mix": 0}
    item2id = {"Video_Games::vg_a": 0, "Video_Games::vg_b": 1, "Video_Games::vg_c": 2,
               "Video_Games::vg_d": 3, "Video_Games::vg_e": 4}

    oracle_result = compute_memory_oracle(
        interactions, "u_mix", user2id, item2id, meta_df,
        top_n_categories=5, recent_n=10,
        love_min_rating=4, hate_max_rating=2,
        top_n_loved_items=10, top_n_hated_items=10
    )

    # Love: ratings 5 and 4 (vg_a, vg_b)
    assert "Video_Games::vg_a" in oracle_result["loved_items"]
    assert "Video_Games::vg_b" in oracle_result["loved_items"]
    assert "Video_Games::vg_c" not in oracle_result["loved_items"]  # rating 3

    # Hate: ratings 2 and 1 (vg_d, vg_e)
    assert "Video_Games::vg_d" in oracle_result["hated_items"]
    assert "Video_Games::vg_e" in oracle_result["hated_items"]
    assert "Video_Games::vg_c" not in oracle_result["hated_items"]  # rating 3


def test_oracle_with_as_of_timestamp(meta_df):
    """Test oracle respects as_of_timestamp filtering."""
    early_interactions = pd.DataFrame({
        "user_id": ["u_snapshot"] * 5,
        "item_id": ["Video_Games::vg_a", "Video_Games::vg_b", "Video_Games::vg_c",
                   "Video_Games::vg_d", "Video_Games::vg_e"],
        "user_idx": [0] * 5,
        "item_idx": [0, 1, 2, 3, 4],
        "rating": [5] * 5,
        "timestamp": [0, 1, 2, 3, 4],
    })

    late_interactions = pd.DataFrame({
        "user_id": ["u_snapshot"] * 5,
        "item_id": ["Video_Games::vg_a", "Video_Games::vg_b", "Video_Games::vg_c",
                   "Video_Games::vg_d", "Video_Games::vg_e"],
        "user_idx": [0] * 5,
        "item_idx": [0, 1, 2, 3, 4],
        "rating": [1] * 5,
        "timestamp": [5, 6, 7, 8, 9],
    })

    interactions = pd.concat([early_interactions, late_interactions])
    user2id = {"u_snapshot": 0}
    item2id = {"Video_Games::vg_a": 0, "Video_Games::vg_b": 1, "Video_Games::vg_c": 2,
               "Video_Games::vg_d": 3, "Video_Games::vg_e": 4}

    oracle_result = compute_memory_oracle(
        interactions, "u_snapshot", user2id, item2id, meta_df,
        top_n_categories=5, recent_n=10, as_of_timestamp=4,
        love_min_rating=4, hate_max_rating=2,
        top_n_loved_items=10, top_n_hated_items=10
    )

    # Should only see interactions up to timestamp 4 (rating 5)
    assert oracle_result["n_interactions"] == 5
    assert "Video_Games::vg_a" in oracle_result["loved_items"]
    assert "Video_Games::vg_a" not in oracle_result["hated_items"]


def test_oracle_unknown_user(meta_df):
    """Test oracle returns empty profile for unknown user."""
    interactions = pd.DataFrame({
        "user_id": ["u1"] * 3,
        "item_id": ["Video_Games::vg_a", "Video_Games::vg_b", "Video_Games::vg_c"],
        "user_idx": [0] * 3,
        "item_idx": [0, 1, 2],
        "rating": [5, 4, 5],
        "timestamp": [0, 1, 2],
    })
    user2id = {"u1": 0}
    item2id = {"Video_Games::vg_a": 0, "Video_Games::vg_b": 1, "Video_Games::vg_c": 2}

    oracle_result = compute_memory_oracle(
        interactions, "unknown", user2id, item2id, meta_df,
        top_n_categories=5, recent_n=10,
        love_min_rating=4, hate_max_rating=2,
        top_n_loved_items=10, top_n_hated_items=10
    )

    assert oracle_result["known"] is False
    assert oracle_result["n_interactions"] == 0
    assert oracle_result["top_categories"] == []
    assert oracle_result["price_range"] is None
    assert oracle_result["recent_items"] == []
    assert oracle_result["love_categories"] == []
    assert oracle_result["hate_categories"] == []
    assert oracle_result["loved_items"] == []
    assert oracle_result["hated_items"] == []
