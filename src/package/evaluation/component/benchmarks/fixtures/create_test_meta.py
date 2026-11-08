"""Raw item metadata for correctness testing."""

from __future__ import annotations

import pandas as pd


def create_test_meta() -> pd.DataFrame:
    """Raw item metadata. The oracle reads this directly so it never depends on ItemCorpus SQL."""
    # Base items vg_a to vg_o (prices 1.0, 150.0, 300.0 pattern)
    # Null price items
    # Outlier price item
    meta_data = []

    # vg_a to vg_o with alternating prices and categories
    prices = [1.0, 150.0, 300.0, 1.0, 150.0, 300.0, 1.0, 150.0, 300.0, 1.0, 150.0, 300.0, 1.0, 150.0, 300.0]
    categories = ["Action", "Puzzle", "RPG", "Action", "Puzzle", "RPG", "Action", "Puzzle", "RPG", "Action", "Strategy", "Simulation", "Sports", "Racing", "Adventure"]

    for i in range(15):
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