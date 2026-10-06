from __future__ import annotations

import re

from .._limits import SEMANTIC_MAX_QUERY_TOKENS

# Small on purpose: BM25 already down-weights common words; this only removes
# glue words that add noise to an OR query.
_STOPWORDS = frozenset(
    "a an the for with and or of to in on at by from is are be i me my we our you your "
    "want need looking find get some any good best cheap new".split()
)


def _tokenize(query: str) -> list[str]:
    """Tokenize query for BM25 search."""
    words = re.findall(r"\w+", query.lower())
    kept = [w for w in words if len(w) > 1 and w not in _STOPWORDS]  # prices belong in filters
    return list(dict.fromkeys(kept))[:SEMANTIC_MAX_QUERY_TOKENS]  # de-duplicate, keep order, cap length
