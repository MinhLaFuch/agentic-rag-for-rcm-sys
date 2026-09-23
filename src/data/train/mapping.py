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
    user2id: dict[str, int], item2id: dict[str, int], mapping_dir: str
) -> None:
    """Save ID mappings to JSON files in the specified directory."""
    mapping_path = Path(mapping_dir)
    mapping_path.mkdir(parents=True, exist_ok=True)

    with open(mapping_path / "user2id.json", "w") as f:
        json.dump(user2id, f)

    with open(mapping_path / "item2id.json", "w") as f:
        json.dump(item2id, f)


def load_mappings(mapping_dir: str) -> tuple[dict[str, int], dict[str, int]]:
    """Load ID mappings from JSON files in the specified directory."""
    mapping_path = Path(mapping_dir)

    with open(mapping_path / "user2id.json", "r") as f:
        user2id = json.load(f)

    with open(mapping_path / "item2id.json", "r") as f:
        item2id = json.load(f)

    return user2id, item2id





