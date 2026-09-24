import json
import logging
from pathlib import Path

from .layout import ensure_dir

log = logging.getLogger(__name__)


def save_mappings(
    user2id: dict[str, int], item2id: dict[str, int], output_dir: str | Path
) -> None:
    """Write `user2id.json` and `item2id.json` into `output_dir`."""
    output_dir = ensure_dir(Path(output_dir))
    with open(output_dir / "user2id.json", "w", encoding="utf-8") as f:
        json.dump(user2id, f)
    with open(output_dir / "item2id.json", "w", encoding="utf-8") as f:
        json.dump(item2id, f)
    log.info("Wrote mappings (%d users, %d items) to %s", len(user2id), len(item2id), output_dir)