from __future__ import annotations

import unicodedata


def normalize_query_text(query: str, mode: str = "raw") -> str:
    
    if mode == "raw":
        return query
    if mode != "ascii_fold":
        raise ValueError("query normalization must be raw or ascii_fold")
    query = query.translate(str.maketrans({"®": " ", "™": " ", "©": " ",
                                         "–": "-", "—": "-", "’": "'", "‘": "'"}))
    decomposed = unicodedata.normalize("NFKD", query)
    folded = "".join(c if ord(c) < 128 else " " for c in decomposed if not unicodedata.combining(c))
    return " ".join(folded.split())
