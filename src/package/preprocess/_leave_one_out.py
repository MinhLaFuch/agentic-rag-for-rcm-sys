"""Leave-one-out split theo thời gian."""
import pandas as pd


def leave_one_out_split(df: pd.DataFrame) -> pd.DataFrame:
    # Cần user_idx → phải chạy sau assign_idx
    df = df.sort_values(["user_idx", "timestamp"]).copy()
    rank_from_end = df.groupby("user_idx").cumcount(ascending=False)
    df["split"] = "train"
    df.loc[rank_from_end == 0, "split"] = "test"
    df.loc[rank_from_end == 1, "split"] = "val"
    return df
