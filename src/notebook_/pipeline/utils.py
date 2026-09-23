"""Backward-compatible wrapper for the shared package helper utilities."""
import pandas as pd


def get_user_history(interactions: pd.DataFrame, user_idx: int, split: str = "train") -> list[int]:
    df = interactions[interactions.user_idx == user_idx]
    if split is not None:
        df = df[df.split == split]
    return df.sort_values("timestamp")["item_idx"].tolist()
