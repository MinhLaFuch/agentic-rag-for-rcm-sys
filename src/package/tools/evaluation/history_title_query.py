"""Balanced lexical history input; no target or holdout fields are accepted."""
from itertools import zip_longest

from .normalize_query_text import normalize_query_text
from ..retrieval.tokenize_search_query import tokenize_search_query


def history_title_query(titles):
    if len(titles)==1:
        return normalize_query_text(titles[0] or '', 'ascii_fold')
    tokens=[tokenize_search_query(normalize_query_text(title or '', 'ascii_fold')) for title in titles]
    balanced=list(dict.fromkeys(token for column in zip_longest(*tokens) for token in column if token))
    # Apply the existing runtime tokenizer's global cap, never increase it.
    return ' '.join(tokenize_search_query(' '.join(balanced)))
