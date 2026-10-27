"""Public entry point for the exact tokenizer used by lexical retrieval."""
from ._helper import _tokenize


def tokenize_search_query(query: str) -> list[str]:
    return _tokenize(query)
