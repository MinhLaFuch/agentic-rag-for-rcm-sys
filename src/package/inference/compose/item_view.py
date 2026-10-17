"""The item as shown to the LLM."""

from __future__ import annotations

from typing import Any

from .._schema import ITEM_FIELDS
from .cut_title import cut_title


def item_view(item: dict[str, Any]) -> dict[str, Any]:
    """The item as shown to the LLM: every field, title cut."""
    view = {f: item.get(f) for f in ITEM_FIELDS}
    if isinstance(view["title"], str):
        view["title"] = cut_title(view["title"])
    return view
