import logging

import pandas as pd

from ..train import user_history
from .layout import ExportDirs, ensure_dir

log = logging.getLogger(__name__)


def write_products(
    meta_df: pd.DataFrame,
    item_map: dict,
    history: pd.DataFrame,
    category: str,
    workspace: str | None = None,
) -> pd.DataFrame:
    """Section 7: `products.ftr` and `products.csv`."""
    out = ensure_dir(ExportDirs(category, workspace).processed)
    products = meta_df[meta_df["item_id"].isin(item_map.keys())]
    products = products.drop_duplicates(subset=["item_id"], keep="first").reset_index(drop=True)
    products = products.copy()
    products["item_id"] = products["item_id"].map(item_map)
    item_count = user_history(history).explode().value_counts()
    products = products.rename(columns={"item_id": "id"})
    products["visited_num"] = products["id"].map(item_count).fillna(0).astype(int)
    products.to_feather(out / "products.ftr")
    products.to_csv(out / "products.csv", index=False, sep="|")
    log.info("Wrote %d products to %s", len(products), out)
    return products