from __future__ import annotations

import re
from pathlib import Path

from ...utils.path import raw_dir


def _tokens(text: str) -> set[str]:
    """'All_Beauty' / 'all beauty' / 'all-beauty' -> {'all', 'beauty'}."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def list_categories(root: Path | None = None) -> list[str]:
    """Category folder names under `resource/raw`."""
    root = root or raw_dir()
    if not root.is_dir():
        raise FileNotFoundError(f"Raw data directory not found: {root}")
    return sorted(p.name for p in root.iterdir() if p.is_dir())


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
