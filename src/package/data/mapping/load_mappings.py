"""Đọc user2id/item2id đã lưu bởi save_mappings."""

from __future__ import annotations

import json
from pathlib import Path

from ._schema import ITEM2ID_FILE, USER2ID_FILE


def load_mappings(input_dir: str | Path) -> tuple[dict[str, int], dict[str, int]]:
    input_dir = Path(input_dir)
    with open(input_dir / USER2ID_FILE, "r", encoding="utf-8") as f:
        user2id = json.load(f)
    with open(input_dir / ITEM2ID_FILE, "r", encoding="utf-8") as f:
        item2id = json.load(f)
    return user2id, item2id
