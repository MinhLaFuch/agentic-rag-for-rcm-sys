from __future__ import annotations

from ...data import ITEM_ID_SEPARATOR
from .._dataclass import AgentOutcome
from ._helper import _BARE_ASIN, _check_numbers, ids_in_text


def check_grounding(
    text: str, mentioned: list[str], outcome: AgentOutcome, *, check_numbers: bool, price_tolerance: float,
) -> str | None:
    """None when the text is grounded in the outcome's items; otherwise one sentence saying what is wrong (also used as the retry notice)."""
    allowed = [i["item_id"] for i in outcome.items]
    allowed_set = set(allowed)
    in_text = ids_in_text(text)
    foreign = [i for i in dict.fromkeys([*in_text, *mentioned]) if i not in allowed_set]
    if foreign:
        return f"id(s) not in the product list: {foreign}. Only these ids exist: {allowed}"
    if set(mentioned) != set(in_text):
        return f"mentioned_item_ids {mentioned} does not match the ids written in the answer {in_text}"
    if in_text != allowed:
        return f"the answer must present exactly these products, in this order: {allowed}; it presents: {in_text}"
    asins = {i.split(ITEM_ID_SEPARATOR, 1)[1] for i in allowed if ITEM_ID_SEPARATOR in i}
    bare = [m.group(0) for m in _BARE_ASIN.finditer(text) if m.group(0) not in asins]
    if bare:
        return f"product code(s) not in the product list: {bare}"
    if check_numbers:
        return _check_numbers(text, outcome, price_tolerance)
    return None
