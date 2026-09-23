import re

def _tokens(text: str) -> set[str]:
    """'All_Beauty' / 'all beauty' / 'all-beauty' -> {'all', 'beauty'}."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))