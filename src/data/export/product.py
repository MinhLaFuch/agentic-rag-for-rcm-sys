import pandas as pd
from pathlib import Path
from ..train import user_history

def _out_dir(category: str, workspace: str | None = None) -> Path:
    """Helper function to determine output directory."""
    if workspace:
        return Path(workspace) / "processed" / category
    return Path("data/processed") / category

def write_products(
    meta_df: pd.DataFrame,
    item_map: dict,
    history: pd.DataFrame,
    category: str,
    workspace: str | None = None,
) -> pd.DataFrame:
    """Section 7: `products.ftr` and `products.csv`."""
    out = _out_dir(category, workspace)
    out.mkdir(parents=True, exist_ok=True)
    products = meta_df[meta_df["item_id"].isin(item_map.keys())]
    products = products.drop_duplicates(subset=["item_id"], keep="first").reset_index(drop=True)
    products = products.copy()
    products["item_id"] = products["item_id"].map(item_map)
    item_count = user_history(history).explode().value_counts()
    products = products.rename(columns={"item_id": "id"})
    products["visited_num"] = products["id"].map(item_count).fillna(0).astype(int)
    products.to_feather(out / "products.ftr")
    products.to_csv(out / "products.csv", index=False, sep="|")
    return products