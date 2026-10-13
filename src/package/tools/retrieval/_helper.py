from __future__ import annotations

import re

from .._limits import SEMANTIC_MAX_QUERY_TOKENS
from ..base import ToolInputError
from ._schema import STOPWORDS

# Small on purpose: BM25 already down-weights common words; this only removes
# glue words that add noise to an OR query.



def _tokenize(query: str) -> list[str]:
    """
    Tokenize query for BM25 search.

    Rules:
    - Keep hyphenated tokens (e.g., "usb-c" becomes ["usb-c"]) and alphanumeric model tokens ("4k", "2tb")
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

    # Keep hyphenated tokens by matching word chars and hyphens. A token may START with a digit ("4k", "1080p",
    # "2tb", "20-inch"): starting at a letter would chop "2tb" into "tb". Pure numbers are dropped below.
    words = re.findall(r"[a-z0-9][a-z0-9-]*", query.lower())
    kept = [
        w for w in words
        if len(w) > 1 and w not in STOPWORDS and not w.replace("-", "").isdigit()
    ]
    return list(dict.fromkeys(kept))[:SEMANTIC_MAX_QUERY_TOKENS]  # de-duplicate, keep order, cap length
