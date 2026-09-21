import re
from pathlib import Path
from ._amazon import AmazonCategory


def _tokens(text: str) -> set[str]:
    """'All_Beauty' / 'all beauty' / 'all-beauty' -> {'all', 'beauty'}."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def list_categories(raw_dir: Path) -> list[str]:
    """Names of all category folders under the Amazon raw directory."""
    if not raw_dir.is_dir():
        raise FileNotFoundError(f"Amazon raw directory not found: {raw_dir}")
    return sorted(p.name for p in raw_dir.iterdir() if p.is_dir())


def resolve_category(query: str, raw_dir: Path, processed_dir: Path) -> AmazonCategory:
    """
    Find the category folder that matches `query`.

    Matching order (case-insensitive, ignores _ - and spaces):
      1. exact match:  "all_beauty" -> All_Beauty
      2. token match:  "beauty"     -> All_Beauty (query words all appear in the folder name)
    Raises ValueError if nothing matches or the query is ambiguous.
    """
    folders = list_categories(raw_dir)
    query_tokens = _tokens(query)
    if not query_tokens:
        raise ValueError("Category must not be empty.")

    exact = [f for f in folders if _tokens(f) == query_tokens]
    matches = exact or [f for f in folders if query_tokens <= _tokens(f)]

    if not matches:
        raise ValueError(f"No Amazon category matches {query!r}. Available: {folders}")
    if len(matches) > 1:
        raise ValueError(f"{query!r} is ambiguous, it matches {matches}. Be more specific.")

    name = matches[0]
    category_dir = raw_dir / name
    review_file = category_dir / f"{name}.jsonl.gz"
    meta_file = category_dir / f"meta_{name}.jsonl.gz"
    for f in (review_file, meta_file):
        if not f.exists():
            raise FileNotFoundError(f"Missing file for category {name!r}: {f}")

    return AmazonCategory(
        name=name,
        raw_dir=category_dir,
        review_file=review_file,
        meta_file=meta_file,
        processed_dir=processed_dir / name,
    )