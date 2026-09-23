from pathlib import Path
import json

def _out_dir(category: str, workspace: str | None = None) -> Path:
    """Helper function to determine output directory."""
    if workspace:
        return Path(workspace) / "mapped" / category
    return Path("data/mapped") / category

def write_id_maps(
    item_map: dict, user_map: dict, category: str, workspace: str | None = None
) -> Path:
    """Section 5: `map.json`."""
    path = _out_dir(category, workspace) / "map.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        json.dump({"item": item_map, "user": user_map}, stream)
    return path