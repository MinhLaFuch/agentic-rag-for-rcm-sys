"""Chronological leave-one-out splits."""
import pandas as pd


def split_leave_one_out(data: pd.DataFrame, columns: list[str]):
    ordered = data.sort_values(["user_id", "timestamp"]).reset_index(drop=True)
    test = ordered.groupby("user_id", as_index=False).nth(-1)
    train = ordered.iloc[ordered.index.difference(test.index)]
    return train.reset_index(drop=True)[columns], test.reset_index(drop=True)[columns]


def leave_one_out_split(df: pd.DataFrame):
    history, test = split_leave_one_out(df, ["user_id", "item_id", "timestamp"])
    train, valid = split_leave_one_out(history, ["user_id", "item_id"])
    return train, valid, test, history
