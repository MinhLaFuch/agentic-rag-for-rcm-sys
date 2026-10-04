from __future__ import annotations

import re

from ._config import MAX_QUERY_TOKENS, _STOPWORDS


def _tokenize(query: str) -> list[str]:
    """Tokenize query for BM25 search."""
    words = re.findall(r"\w+", query.lower())
    kept = [w for w in words if len(w) > 1 and w not in _STOPWORDS]  # prices belong in filters
    return list(dict.fromkeys(kept))[:MAX_QUERY_TOKENS]  # de-duplicate, keep order, cap length
