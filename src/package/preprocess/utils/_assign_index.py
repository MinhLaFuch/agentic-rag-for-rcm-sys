"""Gán user_idx / item_idx liên tục."""
import pandas as pd


def assign_idx(df: pd.DataFrame) -> tuple[pd.DataFrame, dict, dict]:
    # indexing from 0..N-1, không nhảy cóc (bài học từ bug lúc test run.py)
    user2idx = {u: i for i, u in enumerate(sorted(df["user_id"].unique()))}
    item2idx = {p: i for i, p in enumerate(sorted(df["parent_asin"].unique()))}
    df = df.copy()
    df["user_idx"] = df["user_id"].map(user2idx)
    df["item_idx"] = df["parent_asin"].map(item2idx)
    return df, user2idx, item2idx
