from pathlib import Path
import json

def load_mappings(input_dir: str | Path) -> tuple[dict[str, int], dict[str, int]]:
    input_dir = Path(input_dir)
    with open(input_dir / "user2id.json", "r", encoding="utf-8") as f:
        user2id = json.load(f)
    with open(input_dir / "item2id.json", "r", encoding="utf-8") as f:
        item2id = json.load(f)
    return user2id, item2id