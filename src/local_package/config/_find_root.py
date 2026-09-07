from pathlib import Path
from typing import Optional


def find_repo_root(file: str, marker: str = "pyproject.toml") -> Optional[Path]:
    """
    Walk up from `file` until a directory containing `marker` is found.
    Returns None if not found (instead of raising), so the caller can fall back.
    """
    path = Path(file).resolve()
    for parent in path.parents:
        if (parent / marker).exists():
            return parent
    return None