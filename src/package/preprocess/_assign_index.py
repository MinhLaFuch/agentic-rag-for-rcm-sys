"""Map raw user and item identifiers to the notebook's 1-based IDs."""
import pandas as pd


def assign_idx(df: pd.DataFrame) -> tuple[pd.DataFrame, dict, dict]:
    user2idx = {user: index for index, user in enumerate(df["user_id"].unique(), 1)}
    item2idx = {item: index for index, item in enumerate(df["item_id"].unique(), 1)}
    df = df.copy()
    df["user_id"] = df["user_id"].map(user2idx)
    df["item_id"] = df["item_id"].map(item2idx)
    return df, user2idx, item2idx
