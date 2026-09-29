"""
ID mapping: chuyển user_id/parent_asin gốc (string) thành integer index
liên tục (0..N-1) — cần cho hầu hết model (embedding lookup table).

Mapping phải được lưu lại (save_mappings/load_mappings) để đảm bảo
reproducibility — mục XXII yêu cầu lưu model version/data version, và
mapping chính là một phần của "data version" đó.
"""

from __future__ import annotations

import json
from pathlib import Path


def save_mappings(
    user2id: dict[str, int], item2id: dict[str, int], output_dir: str | Path
) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "user2id.json", "w", encoding="utf-8") as f:
        json.dump(user2id, f)
    with open(output_dir / "item2id.json", "w", encoding="utf-8") as f:
        json.dump(item2id, f)
