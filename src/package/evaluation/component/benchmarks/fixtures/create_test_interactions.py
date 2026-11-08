"""Create synthetic interaction data for correctness testing."""

from __future__ import annotations

import pandas as pd

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

    # u_love_hate_mix: ratings 5,4,3,2,1 to test love/hate thresholds
    interactions.extend([
        {"user_id": "u_love_hate_mix", "item_id": "Video_Games::vg_a", "user_idx": 11, "item_idx": 0, "rating": 5, "timestamp": 0},
        {"user_id": "u_love_hate_mix", "item_id": "Video_Games::vg_b", "user_idx": 11, "item_idx": 1, "rating": 4, "timestamp": 1},
        {"user_id": "u_love_hate_mix", "item_id": "Video_Games::vg_c", "user_idx": 11, "item_idx": 2, "rating": 3, "timestamp": 2},
        {"user_id": "u_love_hate_mix", "item_id": "Video_Games::vg_d", "user_idx": 11, "item_idx": 3, "rating": 2, "timestamp": 3},
        {"user_id": "u_love_hate_mix", "item_id": "Video_Games::vg_e", "user_idx": 11, "item_idx": 4, "rating": 1, "timestamp": 4},
    ])

    # u_all_love: all ratings >=4
    interactions.extend([
        {"user_id": "u_all_love", "item_id": "Video_Games::vg_a", "user_idx": 12, "item_idx": 0, "rating": 5, "timestamp": 0},
        {"user_id": "u_all_love", "item_id": "Video_Games::vg_b", "user_idx": 12, "item_idx": 1, "rating": 4, "timestamp": 1},
        {"user_id": "u_all_love", "item_id": "Video_Games::vg_c", "user_idx": 12, "item_idx": 2, "rating": 5, "timestamp": 2},
    ])

    # u_all_hate: all ratings <=2
    interactions.extend([
        {"user_id": "u_all_hate", "item_id": "Video_Games::vg_a", "user_idx": 13, "item_idx": 0, "rating": 2, "timestamp": 0},
        {"user_id": "u_all_hate", "item_id": "Video_Games::vg_b", "user_idx": 13, "item_idx": 1, "rating": 1, "timestamp": 1},
        {"user_id": "u_all_hate", "item_id": "Video_Games::vg_c", "user_idx": 13, "item_idx": 2, "rating": 2, "timestamp": 2},
    ])

    # u_no_rating: interactions without rating column (will be added later via column drop)
    interactions.extend([
        {"user_id": "u_no_rating", "item_id": "Video_Games::vg_a", "user_idx": 14, "item_idx": 0, "rating": 5, "timestamp": 0},
        {"user_id": "u_no_rating", "item_id": "Video_Games::vg_b", "user_idx": 14, "item_idx": 1, "rating": 4, "timestamp": 1},
    ])

    # u_mixed_ratings: ratings 5,4,3,2,1 with distinct items
    interactions.extend([
        {"user_id": "u_mixed_ratings", "item_id": "Video_Games::vg_a", "user_idx": 15, "item_idx": 0, "rating": 5, "timestamp": 0},
        {"user_id": "u_mixed_ratings", "item_id": "Video_Games::vg_b", "user_idx": 15, "item_idx": 1, "rating": 4, "timestamp": 1},
        {"user_id": "u_mixed_ratings", "item_id": "Video_Games::vg_c", "user_idx": 15, "item_idx": 2, "rating": 3, "timestamp": 2},
        {"user_id": "u_mixed_ratings", "item_id": "Video_Games::vg_d", "user_idx": 15, "item_idx": 3, "rating": 2, "timestamp": 3},
        {"user_id": "u_mixed_ratings", "item_id": "Video_Games::vg_e", "user_idx": 15, "item_idx": 4, "rating": 1, "timestamp": 4},
    ])

    # u_boundary_love: rating exactly 4.0 (boundary for love)
    interactions.extend([
        {"user_id": "u_boundary_love", "item_id": "Video_Games::vg_a", "user_idx": 16, "item_idx": 0, "rating": 4, "timestamp": 0},
        {"user_id": "u_boundary_love", "item_id": "Video_Games::vg_b", "user_idx": 16, "item_idx": 1, "rating": 3, "timestamp": 1},
    ])

    # u_boundary_hate: rating exactly 2.0 (boundary for hate)
    interactions.extend([
        {"user_id": "u_boundary_hate", "item_id": "Video_Games::vg_a", "user_idx": 17, "item_idx": 0, "rating": 3, "timestamp": 0},
        {"user_id": "u_boundary_hate", "item_id": "Video_Games::vg_b", "user_idx": 17, "item_idx": 1, "rating": 2, "timestamp": 1},
    ])

    # u_large_recent: 15 interactions to test recent_items capping at 10
    for i in range(15):
        interactions.append({
            "user_id": "u_large_recent",
            "item_id": f"Video_Games::vg_{chr(97 + i)}",  # vg_a to vg_o
            "user_idx": 18,
            "item_idx": i,
            "rating": 5,
            "timestamp": i,
        })

    # u_many_categories: 15 interactions across 5 distinct categories (Action, Puzzle, RPG, Strategy, Simulation cycling)
    categories_cycle = ["Action", "Puzzle", "RPG", "Strategy", "Simulation"]
    for i in range(15):
        interactions.append({
            "user_id": "u_many_categories",
            "item_id": f"Video_Games::vg_{chr(97 + i)}",
            "user_idx": 19,
            "item_idx": i,
            "rating": 5,
            "timestamp": i,
        })

    # u_single_category: 5 interactions all in Action
    for i in range(5):
        interactions.append({
            "user_id": "u_single_category",
            "item_id": f"Video_Games::vg_{chr(97 + i)}",
            "user_idx": 20,
            "item_idx": i,
            "rating": 5,
            "timestamp": i,
        })

    return pd.DataFrame(interactions)

