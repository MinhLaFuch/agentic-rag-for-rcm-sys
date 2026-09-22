"""Map a file path to the forked-repo submodule it lives in, via the host's .gitmodules."""
from __future__ import annotations

import configparser
from pathlib import Path


def submodule_name(host_root: Path, start: Path) -> str | None:
    """
    If `start` sits inside a submodule declared in `host_root/.gitmodules`, return that
    submodule's folder name (e.g. "RecAI"). Returns None if `start` is in the host repo
    itself, or .gitmodules has no entry covering it.
    """
    gitmodules = host_root / ".gitmodules"
    if not gitmodules.is_file():
        return None

    try:
        rel_start = start.resolve().relative_to(host_root.resolve())
    except ValueError:
        return None  # start isn't under host_root at all

    config = configparser.ConfigParser()
    config.read(gitmodules)

    for section in config.sections():
        sub_path = config[section].get("path")
        if not sub_path:
            continue
        sub_path = Path(sub_path)
        if rel_start == sub_path or sub_path in rel_start.parents:
            return sub_path.name

    return None