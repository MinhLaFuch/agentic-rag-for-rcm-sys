"""Lưu user2id/item2id ra JSON (đối xứng với load_mappings)."""

from __future__ import annotations

import json
from pathlib import Path

from ._schema import ITEM2ID_FILE, USER2ID_FILE


def save_mappings(
    user2id: dict[str, int], item2id: dict[str, int], output_dir: str | Path
) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / USER2ID_FILE, "w", encoding="utf-8") as f:
        json.dump(user2id, f)
    with open(output_dir / ITEM2ID_FILE, "w", encoding="utf-8") as f:
        json.dump(item2id, f)
