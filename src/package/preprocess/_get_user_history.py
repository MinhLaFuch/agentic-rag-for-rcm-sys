"""Return a user's chronological history from notebook-compatible data."""
import pandas as pd


def get_user_history(
    interactions: pd.DataFrame, user_idx: int, split: str | None = "train"
) -> list[int]:
    user_column = "user_id" if "user_id" in interactions else "user_idx"
    item_column = "item_id" if "item_id" in interactions else "item_idx"
    df = interactions[interactions[user_column] == user_idx]
    if split is not None and "split" in interactions:
        df = df[df["split"] == split]
    return df.sort_values("timestamp")[item_column].tolist()
