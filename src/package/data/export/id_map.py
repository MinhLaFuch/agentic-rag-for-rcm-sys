import json
import logging
from pathlib import Path

from .layout import ExportDirs, ensure_dir

log = logging.getLogger(__name__)


def write_id_maps(
    item_map: dict, user_map: dict, category: str, workspace: str | None = None
) -> Path:
    """Section 5: `map.json`."""
    path = ensure_dir(ExportDirs(category, workspace).mapped) / "map.json"
    with path.open("w", encoding="utf-8") as stream:
        json.dump({"item": item_map, "user": user_map}, stream)
    log.info("Wrote %s (%d items, %d users)", path, len(item_map), len(user_map))
    return path