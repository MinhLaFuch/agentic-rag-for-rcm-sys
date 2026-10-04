"""
In một giá trị trong configs/ ra stdout — để các script .sh đọc config
thay vì hard-code.

    python -m package.config domains.domains        # mỗi domain một dòng
    python -m package.config run_tag.tag
    python -m package.config data_paths.paths.raw_dir

Phần đầu của key là tên file yaml (domains, run_tag, data_paths, baselines, ...).
List of dict có field ``name`` được in ra theo ``name``.
"""

from __future__ import annotations

import sys

from .loader import load_config


def _lookup(key: str):
    name, *path = key.split(".")
    value = load_config(name)
    for part in path:
        value = value[part]
    return value


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    try:
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
