"""K-core filtering."""
import pandas as pd


def kcore_filter(df: pd.DataFrame, min_interactions: int = 5) -> pd.DataFrame:
    # Lặp tới khi ổn định — lọc user có thể làm item tụt ngưỡng, và ngược lại
    while True:
        before = len(df)
        user_ok = df.groupby("user_id").size()
        df = df[df["user_id"].isin(user_ok[user_ok >= min_interactions].index)]
        item_ok = df.groupby("parent_asin").size()
        df = df[df["parent_asin"].isin(item_ok[item_ok >= min_interactions].index)]
        if len(df) == before:
            break
    return df
