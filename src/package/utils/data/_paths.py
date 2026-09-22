from __future__ import annotations

import re
from pathlib import Path

from ._config import PROCESSED_DIR, RAW_DIR


def _tokens(text: str) -> set[str]:
    """'All_Beauty' / 'all beauty' / 'all-beauty' -> {'all', 'beauty'}."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def list_categories(raw_dir: Path | None = None) -> list[str]:
    """Names of all category folders under `raw_dir` (defaults to RAW_DIR)."""
    raw_dir = raw_dir or RAW_DIR
    if not raw_dir.is_dir():
        raise FileNotFoundError(f"Raw data directory not found: {raw_dir}")
    return sorted(p.name for p in raw_dir.iterdir() if p.is_dir())


def category_name(query: str) -> str:
    """'beauty' -> 'All_Beauty'. Raises if nothing matches or the name is ambiguous."""
    folders = list_categories()
    query_tokens = _tokens(query)
    if not query_tokens:
        raise ValueError("Category must not be empty.")

    exact = [f for f in folders if _tokens(f) == query_tokens]
    matches = exact or [f for f in folders if query_tokens <= _tokens(f)]

    if not matches:
        raise ValueError(f"No category matches {query!r}. Available: {folders}")
    if len(matches) > 1:
        raise ValueError(f"{query!r} is ambiguous, it matches {matches}. Be more specific.")
    return matches[0]


def raw_dir(query: str) -> Path:
    return RAW_DIR / category_name(query)


def review_file(query: str) -> Path:
    name = category_name(query)
    path = raw_dir(query) / f"{name}.jsonl.gz"
    if not path.exists():
        raise FileNotFoundError(f"Missing review file for category {name!r}: {path}")
    return path


def meta_file(query: str) -> Path:
    name = category_name(query)
    path = raw_dir(query) / f"meta_{name}.jsonl.gz"
    if not path.exists():
        raise FileNotFoundError(f"Missing meta file for category {name!r}: {path}")
    return path


def processed_dir(query: str) -> Path:
    return PROCESSED_DIR / category_name(query)