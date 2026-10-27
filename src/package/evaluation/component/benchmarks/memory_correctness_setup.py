"""Setup test data for MemoryTool correctness benchmark."""

from __future__ import annotations

import pandas as pd

from package.tools.corpus import ItemCorpus
from package.memory.memory_tool import MemoryTool


def create_test_interactions() -> pd.DataFrame:
    """Create synthetic interaction data for correctness testing."""
    interactions = []

    # u_short: 2 interactions
    interactions.extend([
        {"user_id": "u_short", "item_id": "Video_Games::vg_a", "user_idx": 0, "item_idx": 0, "rating": 5, "timestamp": 0},
        {"user_id": "u_short", "item_id": "Video_Games::vg_b", "user_idx": 0, "item_idx": 1, "rating": 4, "timestamp": 1},
    ])

    # u_long: 10 interactions
    for i in range(10):
        interactions.append({
            "user_id": "u_long",
            "item_id": f"Video_Games::vg_{chr(97 + i)}",  # vg_a to vg_j
            "user_idx": 1,
            "item_idx": i,
            "rating": 5,
            "timestamp": i,
        })

    # u_cutoff users: 5 interactions each with timestamps 0-4
    for user_id, base_idx in [("u_cutoff_before", 2), ("u_cutoff_at", 3), ("u_cutoff_after", 4)]:
        for i in range(5):
            interactions.append({
                "user_id": user_id,
                "item_id": f"Video_Games::vg_{chr(97 + i)}",
                "user_idx": base_idx,
                "item_idx": i,
                "rating": 5,
                "timestamp": i,
            })

    # u_leakage_test: 5 interactions (timestamps 0-4), 2 future interactions (timestamps 5-6)
    for i in range(7):
        interactions.append({
            "user_id": "u_leakage_test",
            "item_id": f"Video_Games::vg_{chr(97 + i)}",
            "user_idx": 5,
            "item_idx": i,
            "rating": 5,
            "timestamp": i,
        })

    # u_tie_categories: 4 interactions with equal category counts
    interactions.extend([
        {"user_id": "u_tie_categories", "item_id": "Video_Games::vg_a", "user_idx": 6, "item_idx": 0, "rating": 5, "timestamp": 0},
        {"user_id": "u_tie_categories", "item_id": "Video_Games::vg_b", "user_idx": 6, "item_idx": 1, "rating": 4, "timestamp": 1},
        {"user_id": "u_tie_categories", "item_id": "Video_Games::vg_c", "user_idx": 6, "item_idx": 2, "rating": 5, "timestamp": 2},
        {"user_id": "u_tie_categories", "item_id": "Video_Games::vg_d", "user_idx": 6, "item_idx": 3, "rating": 4, "timestamp": 3},
    ])

    # u_null_prices: 2 interactions with NULL prices
    interactions.extend([
        {"user_id": "u_null_prices", "item_id": "Video_Games::vg_null_a", "user_idx": 7, "item_idx": 10, "rating": 5, "timestamp": 0},
        {"user_id": "u_null_prices", "item_id": "Video_Games::vg_null_b", "user_idx": 7, "item_idx": 11, "rating": 4, "timestamp": 1},
    ])

    # u_equal_prices: 3 interactions whose items all cost 1.0 (vg_a, vg_d, vg_g)
    interactions.extend([
        {"user_id": "u_equal_prices", "item_id": "Video_Games::vg_a", "user_idx": 8, "item_idx": 0, "rating": 5, "timestamp": 0},
        {"user_id": "u_equal_prices", "item_id": "Video_Games::vg_d", "user_idx": 8, "item_idx": 3, "rating": 4, "timestamp": 1},
        {"user_id": "u_equal_prices", "item_id": "Video_Games::vg_g", "user_idx": 8, "item_idx": 6, "rating": 5, "timestamp": 2},
    ])

    # u_outlier_price: 3 interactions with one outlier
    interactions.extend([
        {"user_id": "u_outlier_price", "item_id": "Video_Games::vg_a", "user_idx": 9, "item_idx": 0, "rating": 5, "timestamp": 0},
        {"user_id": "u_outlier_price", "item_id": "Video_Games::vg_b", "user_idx": 9, "item_idx": 1, "rating": 4, "timestamp": 1},
        {"user_id": "u_outlier_price", "item_id": "Video_Games::vg_outlier", "user_idx": 9, "item_idx": 12, "rating": 5, "timestamp": 2},
    ])

    # u_dup_items: same item bought twice (vg_b at ts 0 and 2) + vg_a once. Probes whether categories are
    # counted per distinct item (tool: SQL `item_id IN (...)`) or per interaction row.
    interactions.extend([
        {"user_id": "u_dup_items", "item_id": "Video_Games::vg_b", "user_idx": 10, "item_idx": 1, "rating": 5, "timestamp": 0},
        {"user_id": "u_dup_items", "item_id": "Video_Games::vg_a", "user_idx": 10, "item_idx": 0, "rating": 4, "timestamp": 1},
        {"user_id": "u_dup_items", "item_id": "Video_Games::vg_b", "user_idx": 10, "item_idx": 1, "rating": 5, "timestamp": 2},
    ])

    return pd.DataFrame(interactions)


def create_test_corpus() -> ItemCorpus:
    """Create synthetic corpus for correctness testing."""
    return ItemCorpus.from_dataframe(create_test_meta())


def create_test_meta() -> pd.DataFrame:
    """Raw item metadata. The oracle reads this directly so it never depends on ItemCorpus SQL."""
    # Base items vg_a to vg_j (prices 1.0, 150.0, 300.0 pattern)
    # Null price items
    # Outlier price item
    meta_data = []

    # vg_a to vg_j with alternating prices
    prices = [1.0, 150.0, 300.0, 1.0, 150.0, 300.0, 1.0, 150.0, 300.0, 1.0]
    categories = ["Action", "Puzzle", "RPG", "Action", "Puzzle", "RPG", "Action", "Puzzle", "RPG", "Action"]

    for i in range(10):
        meta_data.append({
            "parent_asin": f"vg_{chr(97 + i)}",
            "domain": "Video_Games",
            "title": f"Game {chr(65 + i)}",
            "store": "StoreA",
            "price": prices[i],
            "average_rating": 4.0 + (i % 2) * 0.5,
            "rating_number": 50 + i * 10,
            "main_category": categories[i],
            "categories": [categories[i]],
        })

    # Null price items
    meta_data.extend([
        {
            "parent_asin": "vg_null_a",
            "domain": "Video_Games",
            "title": "Null Price Game A",
            "store": "StoreB",
            "price": None,
            "average_rating": 4.0,
            "rating_number": 50,
            "main_category": "Action",
            "categories": ["Action"],
        },
        {
            "parent_asin": "vg_null_b",
            "domain": "Video_Games",
            "title": "Null Price Game B",
            "store": "StoreB",
            "price": None,
            "average_rating": 3.5,
            "rating_number": 30,
            "main_category": "Puzzle",
            "categories": ["Puzzle"],
        },
    ])

    # Outlier price item
    meta_data.append({
        "parent_asin": "vg_outlier",
        "domain": "Video_Games",
        "title": "Outlier Price Game",
        "store": "StoreC",
        "price": 1000.0,
        "average_rating": 4.5,
        "rating_number": 100,
        "main_category": "Action",
        "categories": ["Action"],
    })

    return pd.DataFrame(meta_data)


def create_test_mappings(interactions: pd.DataFrame):
    """Create user2id and item2id mappings from interactions."""
    user_ids = interactions["user_id"].unique()
    item_ids = interactions["item_id"].unique()

    user2id = {uid: idx for idx, uid in enumerate(user_ids)}
    item2id = {iid: idx for idx, iid in enumerate(item_ids)}
    id2item = {idx: iid for iid, idx in item2id.items()}

    # Add u_empty (exists but has no interactions)
    user2id["u_empty"] = len(user2id)

    return user2id, item2id, id2item
