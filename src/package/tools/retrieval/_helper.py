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
    - Non-ASCII characters (including Vietnamese diacritics) are allowed but normalized
    - For Vietnamese: diacritics are preserved but basic Latin matching still works

    Args:
        query: Search query string

    Returns:
        List of unique tokens, order preserved, capped at SEMANTIC_MAX_QUERY_TOKENS
    """
    # Normalize to NFKD to separate diacritics from base characters
    # This allows "chuột" to potentially match similar terms while preserving the original
    import unicodedata
    normalized = unicodedata.normalize('NFKD', query.lower())
    
    # Keep hyphenated tokens by matching word chars and hyphens. A token may START with a digit ("4k", "1080p",
    # "2tb", "20-inch"): starting at a letter would chop "2tb" into "tb". Pure numbers are dropped below.
    # Allow unicode letters in addition to ascii alphanumerics
    words = re.findall(r"[\w-][\w-]*", normalized)
    kept = [
        w for w in words
        if len(w) > 1 and w not in STOPWORDS and not w.replace("-", "").isdigit()
    ]
    return list(dict.fromkeys(kept))[:SEMANTIC_MAX_QUERY_TOKENS]  # de-duplicate, keep order, cap length
