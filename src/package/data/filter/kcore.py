import pandas as pd

def kcore_filter(
    df: pd.DataFrame, user_k: int = 5, item_k: int | None = None, max_iter: int = 20
) -> pd.DataFrame:
    """
    Keep only users with >= user_k interactions and items with >= item_k interactions.
    Iteratively remove users/items until stable or max_iter reached.
    If item_k is None, use the same threshold as user_k.
    """
    item_k = user_k if item_k is None else item_k
    df = df.copy()
    previous = (len(df["user_id"].unique()), len(df["parent_asin"].unique()))
    for _ in range(max_iter):
        users = df["user_id"].value_counts()
        df = df[df["user_id"].isin(users[users >= user_k].index)]
        items = df["parent_asin"].value_counts()
        df = df[df["parent_asin"].isin(items[items >= item_k].index)]
        current = (len(df["user_id"].unique()), len(df["parent_asin"].unique()))
        if current == previous:
            break
        previous = current
    return df.reset_index(drop=True)