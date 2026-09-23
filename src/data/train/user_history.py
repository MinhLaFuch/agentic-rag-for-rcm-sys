import pandas as pd

def user_histories(df: pd.DataFrame) -> pd.Series:
    """item_id list per user, in time order."""
    user_col = "user_id" if "user_id" in df.columns else "user_idx"
    item_col = "item_id" if "item_id" in df.columns else "item_idx"
    ordered = df.sort_values([user_col, "timestamp"]) if "timestamp" in df.columns else df
    return ordered.groupby(user_col)[item_col].agg(list)


def get_user_history(
    df: pd.DataFrame, user_id, split: str | None = None
) -> list:
    """One user's chronological item ids (optionally filtered by a `split` column)."""
    user_col = "user_id" if "user_id" in df.columns else "user_idx"
    item_col = "item_id" if "item_id" in df.columns else "item_idx"
    rows = df[df[user_col] == user_id]
    if split is not None and "split" in df.columns:
        rows = rows[rows["split"] == split]
    if "timestamp" in rows.columns:
        rows = rows.sort_values("timestamp")
    return rows[item_col].tolist()