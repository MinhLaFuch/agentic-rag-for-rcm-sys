from __future__ import annotations

import re

from .._limits import SEMANTIC_MAX_QUERY_TOKENS
from ..base import ToolInputError

# Small on purpose: BM25 already down-weights common words; this only removes
# glue words that add noise to an OR query.
_STOPWORDS = frozenset(
    "a an the for with and or of to in on at by from is are be i me my we our you your "
    "want need looking find get some any good best cheap new under over below".split()
)


def _tokenize(query: str) -> list[str]:
    """
    Tokenize query for BM25 search.

    Rules:
    - Keep hyphenated tokens (e.g., "usb-c" becomes ["usb-c"])
    - Drop pure numbers (prices belong in filters)
    - Drop stopwords (including "under", "over", "below")
    - Query must be ASCII; non-ASCII raises ToolInputError

    Args:
        query: Search query string

    Returns:
        List of unique tokens, order preserved, capped at SEMANTIC_MAX_QUERY_TOKENS

    Raises:
        ToolInputError: If query contains non-ASCII characters
    """
    # Check for non-ASCII characters
    try:
        query.encode("ascii")
    except UnicodeEncodeError:
        raise ToolInputError(
            "`query` must contain only ASCII characters (English text). "
            "Translate non-English queries before searching."
        )

    # Keep hyphenated tokens by matching word chars and hyphens
    words = re.findall(r"[a-z][a-z0-9-]*", query.lower())
    kept = [
        w for w in words
        if len(w) > 1 and w not in _STOPWORDS and not w.replace("-", "").isdigit()
    ]
    return list(dict.fromkeys(kept))[:SEMANTIC_MAX_QUERY_TOKENS]  # de-duplicate, keep order, cap length
