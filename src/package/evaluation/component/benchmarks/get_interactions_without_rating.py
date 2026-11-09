"""Return a copy of interactions for the given user with the rating column dropped."""

from __future__ import annotations

import pandas as pd


def get_interactions_without_rating(interactions: pd.DataFrame, user_id: str) -> pd.DataFrame:
    """Return a copy of interactions for the given user with the rating column dropped."""
    user_interactions = interactions[interactions["user_id"] == user_id].copy()
    if "rating" in user_interactions.columns:
        user_interactions = user_interactions.drop(columns=["rating"])
    return user_interactions