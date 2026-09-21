from pathlib import Path
from typing import Optional, Union


def find_repo_root(file: Union[str, Path], marker: str = "pyproject.toml") -> Optional[Path]:
    """
    Walk up from `file` until a directory containing `marker` is found.
    Returns None if not found (instead of raising), so the caller can fall back.
    """
    path = Path(file).resolve()
    if path.is_file():
        path = path.parent
    for parent in path.parents:
        if (parent / marker).exists():
            return parent
    if (path / marker).exists():
        return path
    return None