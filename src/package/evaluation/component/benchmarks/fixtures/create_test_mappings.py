"""Create user2id and item2id mappings from interactions."""

from __future__ import annotations

import pandas as pd


def create_test_mappings(interactions: pd.DataFrame):
    """Create user2id and item2id mappings from interactions."""
    user_ids = interactions["user_id"].unique()
    item_ids = interactions["item_id"].unique()

    user2id = {uid: idx for idx, uid in enumerate(user_ids)}
    item2id = {iid: idx for idx, iid in enumerate(item_ids)}
    id2item = {idx: iid for iid, idx in item2id.items()}

    # Add u_empty (exists but has no interactions)
    user2id["u_empty"] = len(user2id)

    # Add u_no_rating to user2id mapping (it has interactions in the base dataset)
    if "u_no_rating" not in user2id:
        user2id["u_no_rating"] = len(user2id)

    return user2id, item2id, id2item