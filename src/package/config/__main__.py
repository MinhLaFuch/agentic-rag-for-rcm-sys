"""
In một giá trị trong configs/ hoặc một đường dẫn của project ra stdout — để các script .sh đọc
config/đường dẫn thay vì hard-code.

    python -m package.config domains.domains        # mỗi domain một dòng
    python -m package.config run_tag.tag
    python -m package.config data_paths.paths.raw_dir

    # Đường dẫn đã resolve từ DataPaths (nguồn duy nhất), in tương đối so với gốc project:
    python -m package.config path:filtered_path
    python -m package.config --tag vg_toys path:splits_dir
    python -m package.config path:cleaned_path:Video_Games      # <tên>:<đối số> cho review_path/meta_path/cleaned_path/split_path
    python -m package.config path:split_path:train

Phần đầu của key là tên file yaml (domains, run_tag, data_paths, baselines, ...).
List of dict có field ``name`` được in ra theo ``name``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from ._constants import PROJECT_ROOT
from .get_data_paths import get_data_paths
from .loader import load_config

_PATH_PROPERTIES = (
    "raw_dir", "cleaned_dir", "filtered_dir", "mapped_dir", "splits_dir", "log_dir", "experiments_dir", "filtered_path",
)
_PATH_METHODS = ("review_path", "meta_path", "cleaned_path", "split_path")  # take one argument


def _lookup(key: str):
    name, *path = key.split(".")
    value = load_config(name)
    for part in path:
        value = value[part]
    return value


def _display(path: Path) -> str:
    """Relative to the project root (shell scripts cd there), forward slashes (also on Windows)."""
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _resolve_path(spec: str, tag: str | None) -> str:
    name, _, arg = spec.partition(":")
    paths = get_data_paths(tag)
    if name in _PATH_PROPERTIES and not arg:
        return _display(getattr(paths, name))
    if name in _PATH_METHODS and arg:
        return _display(getattr(paths, name)(arg))
    raise KeyError(f"unknown path spec {spec!r}; properties={_PATH_PROPERTIES}, methods (need :<arg>)={_PATH_METHODS}")


def main(argv: list[str]) -> int:
    tag = None
    if len(argv) == 3 and argv[0] == "--tag":
        tag, argv = argv[1], argv[2:]
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        if argv[0].startswith("path:"):
            print(_resolve_path(argv[0][len("path:"):], tag))
            return 0
        value = _lookup(argv[0])
    except (KeyError, TypeError) as exc:
        print(f"config key not found: {argv[0]} ({exc!r})", file=sys.stderr)
        return 1

    items = value if isinstance(value, list) else [value]
    for item in items:
        print(item["name"] if isinstance(item, dict) and "name" in item else item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
