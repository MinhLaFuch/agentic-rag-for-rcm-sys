from pathlib import Path
import json

def save_mappings(
    user2id: dict[str, int], item2id: dict[str, int], output_dir: str | Path
) -> None:
    """Write `user2id.json` and `item2id.json` into `output_dir`."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "user2id.json", "w", encoding="utf-8") as f:
        json.dump(user2id, f)
    with open(output_dir / "item2id.json", "w", encoding="utf-8") as f:
        json.dump(item2id, f)