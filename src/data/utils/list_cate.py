from pathlib import Path
from utils.path import raw_dir

def list_categories(root: Path | None = None) -> list[str]:
    """Category folder names under `resource/raw`."""
    root = root or raw_dir()
    if not root.is_dir():
        raise FileNotFoundError(f"Raw data directory not found: {root}")
    return sorted(p.name for p in root.iterdir() if p.is_dir())