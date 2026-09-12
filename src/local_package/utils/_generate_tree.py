# src/utils/tree.py
from pathlib import Path
from typing import Union

_IGNORE_LIST = {"__pycache__", "venv", "env", "Scripts", "Lib", "Include"}


def generate_tree(
    dir_path: Union[str, Path], prefix: str = "", _is_root: bool = True
) -> None:
    """
    Print a directory tree, showing only .py files and directories
    that contain at least one .py file.

    Usage:
        from utils.tree import generate_tree
        generate_tree(".")            # current directory
        generate_tree("src/config")   # or any specific path
    """
    path = Path(dir_path)
    if _is_root:
        print(".")
    if not path.is_dir():
        return

    items: list[Path] = []
    for x in path.iterdir():
        if x.name.startswith('.') or x.name in _IGNORE_LIST:
            continue
        if x.is_file() and x.suffix == ".py":
            items.append(x)
        elif x.is_dir() and any(x.rglob("*.py")):
            items.append(x)

    items = sorted(items, key=lambda x: (x.is_file(), x.name.lower()))

    for index, item in enumerate(items):
        is_last = (index == len(items) - 1)
        connector = "└── " if is_last else "├── "

        print(prefix + connector + item.name)

        if item.is_dir():
            new_prefix = prefix + ("    " if is_last else "│   ")
            generate_tree(item, new_prefix, _is_root=False)