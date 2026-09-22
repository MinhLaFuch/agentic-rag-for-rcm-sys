"""Filtering steps used by the notebook preprocessing pipeline."""
import pandas as pd


def keep_first_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only the first interaction per (user_id, item_id) pair."""
    df = df.sort_values(["user_id", "timestamp"]).reset_index(drop=True)
    return df.drop_duplicates(["user_id", "item_id"], keep="first").reset_index(drop=True)


def low_rating_filter(df: pd.DataFrame, rating_threshold: float = 3.0) -> pd.DataFrame:
    """Keep only interactions with rating >= rating_threshold."""
    return df[df["rating"] >= rating_threshold].reset_index(drop=True)


def kcore_filter(
    df: pd.DataFrame, user_k: int = 5, item_k: int | None = None, max_iter: int = 20
) -> pd.DataFrame:
    """
    Keep only users with >= user_k interactions and items with >= item_k interactions.
    Iteratively remove users/items until stable or max_iter reached.
    If item_k is None, use the same threshold as user_k.
    """
    item_k = user_k if item_k is None else item_k
    df = df.copy()
    previous = (len(df["user_id"].unique()), len(df["item_id"].unique()))
    for _ in range(max_iter):
        users = df["user_id"].value_counts()
        df = df[df["user_id"].isin(users[users >= user_k].index)]
        items = df["item_id"].value_counts()
        df = df[df["item_id"].isin(items[items >= item_k].index)]
        current = (len(df["user_id"].unique()), len(df["item_id"].unique()))
        if current == previous:
            break
        previous = current
    return df.reset_index(drop=True)
