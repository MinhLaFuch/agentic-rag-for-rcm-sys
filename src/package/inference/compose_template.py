from __future__ import annotations

from ._dataclass import AgentOutcome, Answer
from ._helper import cut_title
from ._prompt import ID_ONLY_NOTE, NO_RESULT_TEXT, OK_HEADER, PARTIAL_HEADER, TOOL_ERROR_TEXT
from .classify_outcome import classify_outcome
from .empty_usage import empty_usage


def _item_lines(number: int, item: dict) -> list[str]:
    title, item_id = item.get("title"), item["item_id"]
    lines = [f"{number}. {cut_title(title)} ({item_id})" if title else f"{number}. {item_id}"]
    details = []
    if item.get("price") is not None:
        details.append(f"Giá: ${float(item['price']):.2f}")
    if item.get("average_rating") is not None:
        count = f" ({int(item['rating_number'])} lượt)" if item.get("rating_number") is not None else ""
        details.append(f"Đánh giá: {float(item['average_rating']):.1f}/5{count}")
    if item.get("store"):
        details.append(f"Nhà bán: {item['store']}")
    if details:
        lines.append("   " + " · ".join(details))
    elif not title:
        lines.append(f"   {ID_ONLY_NOTE}")
    return lines


def compose_template(outcome: AgentOutcome) -> Answer:
    """Deterministic answer (no LLM) for any outcome: fixed texts for the non-ok statuses, a list of items for ok."""
    status, reason = classify_outcome(outcome)
    base = dict(status=status, composer="template", grounded=True, usage=empty_usage(), reason=reason)
    if status == "ask_user":
        return Answer(text=outcome.question.strip(), **base)
    if status == "no_result":
        return Answer(text=NO_RESULT_TEXT, **base)
    if status == "tool_error":
        return Answer(text=TOOL_ERROR_TEXT, **base)
    header = PARTIAL_HEADER if outcome.errors else OK_HEADER
    lines = [header]
    for number, item in enumerate(outcome.items, 1):
        lines += _item_lines(number, item)
    return Answer(text="\n".join(lines), items=[dict(i) for i in outcome.items], **base)
