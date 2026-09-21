"""Tách bảng canonical ra 4 file chuẩn cho pipeline."""
import json
import os

import pandas as pd


def write_outputs(canonical: pd.DataFrame, user2idx: dict, item2idx: dict, out_dir: str) -> None:
    interactions = canonical[["user_idx", "item_idx", "timestamp", "split"]]
    interactions.to_parquet(os.path.join(out_dir, "interactions.parquet"), index=False)

    item_lookup = (
        canonical[["item_idx", "title", "average_rating", "rating_number", "categories"]]
        .drop_duplicates(subset=["item_idx"])
        .rename(columns={"average_rating": "avg_rating"})
    )
    item_lookup["categories"] = item_lookup["categories"].apply(
        lambda c: " ".join(str(x).replace(" ", "_") for x in c) if isinstance(c, (list, tuple)) else ""
    )
    item_lookup.to_parquet(os.path.join(out_dir, "item_lookup.parquet"), index=False)

    with open(os.path.join(out_dir, "user2idx.json"), "w") as f:
        json.dump(user2idx, f)
    with open(os.path.join(out_dir, "item2idx.json"), "w") as f:
        json.dump(item2idx, f)
