"""Independent oracle for MemoryTool correctness evaluation.

Computes the expected profile from RAW data (interactions DataFrame + item metadata
DataFrame) with plain pandas/Counter. It deliberately does NOT import MemoryTool or
ItemCorpus and does not run any SQL, so a bug in the tool's SQL or filtering cannot
also hide in the oracle.

Semantics encoded here (taken from the tool's documented contract):
- unknown user / no interactions (after the as_of cutoff) -> known=False, empty profile
- n_interactions = number of interaction ROWS of the user (<= as_of_timestamp if given)
- recent_items = up to `recent_n` item ids ordered by timestamp desc (rows, so a repeated
  item can appear twice); item_idx missing from item2id are skipped
- top_categories = categories counted over DISTINCT items in the history, ordered by
  (count desc, category asc), cut to top_n_categories
- price_range = {min, max} over non-null prices of distinct history items, else None
- love_categories = categories of items with rating >= love_min_rating (if rating column exists)
- hate_categories = categories of items with rating <= hate_max_rating (if rating column exists)
- loved_items = items with rating >= love_min_rating, sorted by rating desc, limited to top_n_loved_items
- hated_items = items with rating <= hate_max_rating, sorted by rating asc, limited to top_n_hated_items
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import pandas as pd

DEFAULT_RECENT_N = 10  # = memory.yaml recent_items


def _empty(user_id: str) -> dict[str, Any]:
    return {"user_id": user_id, "known": False, "n_interactions": 0,
            "top_categories": [], "price_range": None, "recent_items": [],
            "love_categories": [], "hate_categories": [], "loved_items": [], "hated_items": []}


def compute_memory_oracle(
    interactions: pd.DataFrame,
    user_id: str,
    user2id: dict[str, int],
    item2id: dict[str, int],
    meta: pd.DataFrame,
    top_n_categories: int = 5,
    as_of_timestamp: int | None = None,
    recent_n: int = DEFAULT_RECENT_N,
    love_min_rating: int = 4,
    hate_max_rating: int = 2,
    top_n_loved_items: int = 10,
    top_n_hated_items: int = 10,
) -> dict[str, Any]:
    """Expected MemoryTool output for one user, computed from raw data only."""
    uidx = user2id.get(user_id)
    if uidx is None:
        return _empty(user_id)

    df = interactions
    if as_of_timestamp is not None:
        df = df[df["timestamp"] <= as_of_timestamp]
    hist = df[df["user_idx"] == uidx]
    if len(hist) == 0:
        return _empty(user_id)

    id2item = {v: k for k, v in item2id.items()}
    hist_sorted = hist.sort_values("timestamp", ascending=False, kind="stable")
    recent_items = [id2item[i] for i in hist_sorted["item_idx"].tolist() if i in id2item][:recent_n]

    distinct_items = {id2item[i] for i in hist["item_idx"].tolist() if i in id2item}

    # per-item metadata straight from the raw frame (namespaced id = domain::parent_asin)
    prices: list[float] = []
    cat_counter: Counter[str] = Counter()
    for row in meta.itertuples(index=False):
        item_id = f"{row.domain}::{row.parent_asin}"
        if item_id not in distinct_items:
            continue
        price = getattr(row, "price", None)
        if price is not None and not pd.isna(price):
            prices.append(float(price))
        cats = getattr(row, "categories", None) or []
        if isinstance(cats, str):
            cats = [cats]
        cat_counter.update({c for c in cats if c})  # set: one count per item per category

    ordered = sorted(cat_counter.items(), key=lambda kv: (-kv[1], kv[0]))

    # Love/hate fields (requires rating column)
    love_categories = []
    hate_categories = []
    loved_items = []
    hated_items = []

    if "rating" in hist.columns:
        # Build item_id -> categories mapping from metadata
        item_to_cats: dict[str, list[str]] = {}
        for row in meta.itertuples(index=False):
            item_id = f"{row.domain}::{row.parent_asin}"
            if item_id not in distinct_items:
                continue
            cats = getattr(row, "categories", None) or []
            if isinstance(cats, str):
                cats = [cats]
            item_to_cats[item_id] = cats

        # Compute love/hate from ratings
        for row in hist.itertuples(index=False):
            item_id = id2item.get(row.item_idx)
            if item_id is None:
                continue
            rating = row.rating
            cats = item_to_cats.get(item_id, [])

            if rating >= love_min_rating:
                love_categories.extend(cats)
                loved_items.append(item_id)
            elif rating <= hate_max_rating:
                hate_categories.extend(cats)
                hated_items.append(item_id)

        # Deduplicate and limit categories
        love_categories = list(dict.fromkeys(love_categories))[:top_n_categories]
        hate_categories = list(dict.fromkeys(hate_categories))[:top_n_categories]

        # Sort items by rating and limit
        item_ratings = hist.groupby("item_idx")["rating"].mean().to_dict()
        loved_items_sorted = sorted(
            set(loved_items),
            key=lambda x: item_ratings.get(item2id.get(x, -1), 0),
            reverse=True
        )[:top_n_loved_items]
        hated_items_sorted = sorted(
            set(hated_items),
            key=lambda x: item_ratings.get(item2id.get(x, -1), 5)
        )[:top_n_hated_items]
    else:
        loved_items_sorted = []
        hated_items_sorted = []

    return {
        "user_id": user_id,
        "known": True,
        "n_interactions": int(len(hist)),
        "top_categories": [c for c, _ in ordered[:top_n_categories]],
        "price_range": {"min": min(prices), "max": max(prices)} if prices else None,
        "recent_items": recent_items,
        "love_categories": love_categories,
        "hate_categories": hate_categories,
        "loved_items": loved_items_sorted,
        "hated_items": hated_items_sorted,
    }


def leakage_probe(
    interactions: pd.DataFrame,
    user_id: str,
    user2id: dict[str, int],
    item2id: dict[str, int],
    as_of_timestamp: int,
    expected_n_interactions: int,
) -> dict[str, Any]:
    """Facts needed to detect future leakage from an output alone (stored in the dataset).

    future_only_items: items the user touched ONLY after the cutoff. If one shows up in
    recent_items, or n_interactions exceeds the allowed count, the profile used future data.
    """
    uidx = user2id.get(user_id)
    id2item = {v: k for k, v in item2id.items()}
    if uidx is None:
        return {"max_n_interactions": expected_n_interactions, "future_only_items": []}
    h = interactions[interactions["user_idx"] == uidx]
    past = {id2item[i] for i in h[h["timestamp"] <= as_of_timestamp]["item_idx"] if i in id2item}
    future = {id2item[i] for i in h[h["timestamp"] > as_of_timestamp]["item_idx"] if i in id2item}
    return {"max_n_interactions": expected_n_interactions, "future_only_items": sorted(future - past)}
