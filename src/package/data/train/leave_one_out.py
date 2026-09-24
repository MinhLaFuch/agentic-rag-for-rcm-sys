"""Per-user history and leave-one-out splits.

Leave-one-out first pulls each user's chronological history, then holds out
items from that history — same as `notebook/process/process.ipynb` section 6:

  1. Sort each user's items by time.
  2. Last item → test; the remaining rows are that user's history.
  3. Last history item → valid; earlier history items → train.

`get_user_history` / `user_histories` read those history rows.
"""
from __future__ import annotations

import pandas as pd
from .user_history import user_history, get_user_history

def split_leave_one_out_seq(
    data: pd.DataFrame,
    user_col: str = "user_id",
    time_col: str = "timestamp",
    columns: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hold out each user's last interaction. The remainder is that user's history."""
    columns = columns or [user_col, "item_id", time_col]
    ordered = data.sort_values([user_col, time_col]).reset_index(drop=True)
    # ``tail`` is typed as returning a DataFrame, unlike ``nth`` which may be
    # inferred as returning either a Series or a DataFrame.
    held_out = ordered.groupby(user_col, as_index=False).tail(1)
    history = ordered.iloc[ordered.index.difference(held_out.index)]
    return (
        history.reset_index(drop=True)[columns],
        held_out.reset_index(drop=True)[columns],
    )


def leave_one_out_split(df: pd.DataFrame):
    """Extract each user's history, then leave-one-out on those history items.

    Returns `(train, valid, test, history)`.
    """
    history, test = split_leave_one_out_seq(
        df, columns=["user_id", "item_id", "timestamp"]
    )
    train, valid = split_leave_one_out_seq(
        history, columns=["user_id", "item_id"]
    )
    return train, valid, test, history
