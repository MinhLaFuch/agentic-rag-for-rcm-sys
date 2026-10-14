"""Grounding checks and reply parsing of the Inference layer."""

from __future__ import annotations

import json
import re
from typing import Any

from ..data import ITEM_ID_SEPARATOR
from ._dataclass import AgentOutcome
from ._schema import ITEM_FIELDS, REASON_CHARS, TITLE_CHARS

_SEP = re.escape(ITEM_ID_SEPARATOR)
_ID = re.compile(rf"(?<![A-Za-z0-9_])[A-Za-z][A-Za-z0-9_]*{_SEP}[A-Za-z0-9_-]*[A-Za-z0-9_]")
_BARE_ASIN = re.compile(r"(?<![A-Za-z0-9_:])B0[0-9A-Z]{8}(?![A-Za-z0-9_])")
_NUM = r"\d+(?:[.,]\d+)*"
_ANY_NUMBER = re.compile(_NUM)
_PRICE = (re.compile(rf"\$\s?({_NUM})"), re.compile(rf"({_NUM})\s?(?:USD|usd|đô la|đô|dollars?)\b"))
_RATING = (re.compile(r"(?<![\d.,])(\d(?:[.,]\d)?)\s*/\s*5\b"), re.compile(r"(?<![\d.,])(\d(?:[.,]\d)?)\s*(?:sao|stars?)\b"))
_EPS = 1e-9


def cut(text: Any, limit: int = REASON_CHARS) -> str:
    return str(text)[:limit]


def cut_title(title: str) -> str:
    title = " ".join(title.split())
    return title if len(title) <= TITLE_CHARS else title[: TITLE_CHARS - 1] + "…"


def item_view(item: dict[str, Any]) -> dict[str, Any]:
    """The item as shown to the LLM: every field, title cut."""
    view = {f: item.get(f) for f in ITEM_FIELDS}
    if isinstance(view["title"], str):
        view["title"] = cut_title(view["title"])
    return view


def parse_llm_reply(text: str) -> tuple[str, list[str]]:
    """(answer, mentioned_item_ids) from the LLM reply; ValueError when it is not the agreed JSON."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())  # models wrap JSON in a fence even in JSON mode
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid_json: the reply is not valid JSON: {text[:150]}") from exc
    if not isinstance(data, dict):
        raise ValueError("invalid_json: the reply must be a JSON object")
    answer, mentioned = data.get("answer"), data.get("mentioned_item_ids")
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("invalid_json: `answer` must be a non-empty string")
    if not isinstance(mentioned, list) or not all(isinstance(i, str) for i in mentioned):
        raise ValueError("invalid_json: `mentioned_item_ids` must be a list of strings")
    return answer, mentioned


def ids_in_text(text: str) -> list[str]:
    """Item ids written in the text, each once, in order of first appearance."""
    return list(dict.fromkeys(m.group(0) for m in _ID.finditer(text)))


def _to_float(raw: str) -> float:
    if "," in raw and "." in raw:
        raw = raw.replace(",", "")
    elif "," in raw:
        parts = raw.split(",")
        raw = raw.replace(",", "") if all(len(p) == 3 for p in parts[1:]) else raw.replace(",", ".")
    return float(raw)


def _numbers(text: str) -> list[float]:
    out = []
    for m in _ANY_NUMBER.finditer(text):
        try:
            out.append(_to_float(m.group(0)))
        except ValueError:
            continue
    return out


def _mentions(patterns: tuple[re.Pattern, ...], text: str) -> list[tuple[str, float]]:
    found = []
    for pattern in patterns:
        for m in pattern.finditer(text):
            try:
                found.append((m.group(1), _to_float(m.group(1))))
            except ValueError:
                continue
    return found


def _check_numbers(text: str, outcome: AgentOutcome, price_tolerance: float) -> str | None:
    known_prices = [float(i["price"]) for i in outcome.items if i.get("price") is not None]
    known_prices += _numbers(outcome.request_text)  # a budget the user stated may be repeated back
    for item in outcome.items:
        known_prices += _numbers(item.get("title") or "")  # so may a number printed in a title
    for raw, value in _mentions(_PRICE, text):
        if not any(abs(value - k) <= price_tolerance + _EPS for k in known_prices):
            return f"the price {raw} is not in the data (known prices: {sorted({k for k in known_prices})[:12]})"
    known_ratings = [round(float(i["average_rating"]), 1) for i in outcome.items if i.get("average_rating") is not None]
    for raw, value in _mentions(_RATING, text):
        if not any(abs(value - r) <= 0.05 + _EPS for r in known_ratings):
            return f"the rating {raw} is not in the data (known ratings: {sorted(set(known_ratings))})"
    return None


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
