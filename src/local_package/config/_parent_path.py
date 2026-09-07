# src/config/_parent_path.py
from pathlib import Path

def find_repo_root(file: str, marker: str = "pyproject.toml") -> Path:
    """
    Walk up from `file` until a directory containing `marker` is found.
    Works no matter how deep `file` is nested — no manual parents[N] counting needed.
    """
    path = Path(file).resolve()
    for parent in path.parents:
        if (parent / marker).exists():
            return parent
    raise FileNotFoundError(f"Could not find repo root (no {marker} found above {file})")