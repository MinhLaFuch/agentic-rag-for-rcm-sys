from .list_cate import list_categories
from ._helper import _tokens

def resolve_category(query: str) -> str:
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