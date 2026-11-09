"""Leakage probe for MemoryTool correctness evaluation."""

from __future__ import annotations

from typing import Any

import pandas as pd


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