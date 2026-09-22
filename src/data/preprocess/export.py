"""Save the same files as `notebook/process/process.ipynb` sections 5–8."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from utils.data.loader import category_name
from utils.path.paths import processed_dir

from .leave_one_out import user_histories


def _out_dir(category: str, workspace: str | None = None) -> Path:
    path = processed_dir(workspace, category_name(category))
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_jsonl(records: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8") as stream:
        for record in records:
            json.dump(record, stream, ensure_ascii=False)
            stream.write("\n")


def write_id_maps(
    item_map: dict, user_map: dict, category: str, workspace: str | None = None
) -> Path:
    """Section 5: `map.json`."""
    path = _out_dir(category, workspace) / "map.json"
    with path.open("w", encoding="utf-8") as stream:
        json.dump({"item": item_map, "user": user_map}, stream)
    return path


def write_splits(
    train: pd.DataFrame,
    valid: pd.DataFrame,
    test: pd.DataFrame,
    history: pd.DataFrame,
    category: str,
    workspace: str | None = None,
) -> Path:
    """Section 6: `train.tsv`, `valid.tsv`, `test.tsv`, `user_history.tsv`."""
    out = _out_dir(category, workspace)
    train.to_csv(out / "train.tsv", index=False)
    valid.to_csv(out / "valid.tsv", index=False)
    test.to_csv(out / "test.tsv", index=False)
    history.to_csv(out / "user_history.tsv", index=False)
    return out


def write_products(
    meta_df: pd.DataFrame,
    item_map: dict,
    history: pd.DataFrame,
    category: str,
    workspace: str | None = None,
) -> pd.DataFrame:
    """Section 7: `products.ftr` and `products.csv`."""
    out = _out_dir(category, workspace)
    products = meta_df[meta_df["item_id"].isin(item_map.keys())]
    products = products.drop_duplicates(subset=["item_id"], keep="first").reset_index(drop=True)
    products = products.copy()
    products["item_id"] = products["item_id"].map(item_map)
    item_count = user_histories(history).explode().value_counts()
    products = products.rename(columns={"item_id": "id"})
    products["visited_num"] = products["id"].map(item_count).fillna(0).astype(int)
    products.to_feather(out / "products.ftr")
    products.to_csv(out / "products.csv", index=False, sep="|")
    return products


def write_simulator_jsonl(
    test: pd.DataFrame,
    history: pd.DataFrame,
    products: pd.DataFrame,
    category: str,
    workspace: str | None = None,
    sample_n: int = 900,
    seed: int = 2024,
    max_history_len: int = 10,
    max_title_len: int = 50,
) -> Path:
    """Section 8: `simulator_test_data_{n}.jsonl`."""
    indexed = products.set_index("id")
    id2title = {
        item_id: str(row.title)[:max_title_len] for item_id, row in indexed.iterrows()
    }
    histories = user_histories(history)
    sample_n = min(sample_n, len(test))
    sampled = test.sample(sample_n, random_state=seed).copy()
    sampled["history"] = sampled["user_id"].map(
        lambda user: "; ".join(
            id2title[item] for item in histories.get(user, [])[-max_history_len:]
        )
    )
    sampled["target"] = sampled["item_id"].map(indexed["title"])
    path = _out_dir(category, workspace) / f"simulator_test_data_{sample_n}.jsonl"
    write_jsonl(sampled[["history", "target"]].to_dict("records"), path)
    return path
