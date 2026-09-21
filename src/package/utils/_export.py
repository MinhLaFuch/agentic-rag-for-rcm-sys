"""Exports for the notebook-compatible preprocessing pipeline."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def write_jsonl(records: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_outputs(
    train: pd.DataFrame,
    valid: pd.DataFrame,
    test: pd.DataFrame,
    history: pd.DataFrame,
    meta_df: pd.DataFrame,
    user_map: dict,
    item_map: dict,
    out_dir: Path,
) -> pd.DataFrame:
    out_dir.mkdir(parents=True, exist_ok=True)
    train.to_csv(out_dir / "train.tsv", index=False)
    valid.to_csv(out_dir / "valid.tsv", index=False)
    test.to_csv(out_dir / "test.tsv", index=False)
    history.to_csv(out_dir / "user_history.tsv", index=False)
    (out_dir / "map.json").write_text(
        json.dumps({"item": item_map, "user": user_map}), encoding="utf-8"
    )

    products = meta_df[meta_df["item_id"].isin(item_map)].drop_duplicates("item_id").copy()
    products["item_id"] = products["item_id"].map(item_map)
    counts = history.groupby("user_id")["item_id"].agg(list).explode().value_counts()
    products = products.rename(columns={"item_id": "id"})
    products["visited_num"] = products["id"].map(counts).fillna(0).astype(int)
    products.to_feather(out_dir / "products.ftr")
    products.to_csv(out_dir / "products.csv", index=False, sep="|")
    return products
