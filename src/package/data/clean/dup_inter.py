"""Filtering steps used by the notebook preprocessing pipeline."""
import pandas as pd

def remove_duplicate_interaction(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only the first interaction per (user_id, item_id) pair."""
    df = df.sort_values(["user_id", "timestamp"]).reset_index(drop=True)
    return df.drop_duplicates(["user_id", "item_id"], keep="first").reset_index(drop=True)






