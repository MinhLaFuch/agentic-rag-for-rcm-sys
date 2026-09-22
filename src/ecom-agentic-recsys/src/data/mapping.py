

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def build_id_mappings(df: pd.DataFrame) -> tuple[dict[str, int], dict[str, int]]:
    unique_users = df["user_id"].drop_duplicates().tolist()
    unique_items = df["parent_asin"].drop_duplicates().tolist()

    user2id = {uid: idx for idx, uid in enumerate(unique_users)}
    item2id = {iid: idx for idx, iid in enumerate(unique_items)}
    return user2id, item2id


def apply_id_mapping(
    df: pd.DataFrame, user2id: dict[str, int], item2id: dict[str, int]
) -> pd.DataFrame:
    """
    Thêm cột `user_idx`, `item_idx`. Ném lỗi rõ ràng nếu gặp id không có
    trong mapping (không được âm thầm bỏ qua — mục XXVIII).
    """
    unknown_users = set(df["user_id"]) - set(user2id.keys())
    unknown_items = set(df["parent_asin"]) - set(item2id.keys())
    if unknown_users or unknown_items:
        raise ValueError(
            f"Found {len(unknown_users)} unknown user_id and "
            f"{len(unknown_items)} unknown parent_asin not present in mapping. "
            "Rebuild mapping from the full dataset before applying."
        )

    out = df.copy()
    out["user_idx"] = out["user_id"].map(user2id)
    out["item_idx"] = out["parent_asin"].map(item2id)
    return out


def save_mappings(
    user2id: dict[str, int], item2id: dict[str, int], output_dir: str | Path
) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "user2id.json", "w", encoding="utf-8") as f:
        json.dump(user2id, f)
    with open(output_dir / "item2id.json", "w", encoding="utf-8") as f:
        json.dump(item2id, f)


def load_mappings(input_dir: str | Path) -> tuple[dict[str, int], dict[str, int]]:
    input_dir = Path(input_dir)
    with open(input_dir / "user2id.json", "r", encoding="utf-8") as f:
        user2id = json.load(f)
    with open(input_dir / "item2id.json", "r", encoding="utf-8") as f:
        item2id = json.load(f)
    return user2id, item2id
