"""Private helpers of the grounding checks (id / price / rating extraction)."""

from __future__ import annotations

import re
from typing import Any

from ...data import ITEM_ID_SEPARATOR
from .._dataclass import AgentOutcome

_SEP = re.escape(ITEM_ID_SEPARATOR)
_ID = re.compile(rf"(?<![A-Za-z0-9_])[A-Za-z][A-Za-z0-9_]*{_SEP}[A-Za-z0-9_-]*[A-Za-z0-9_]")
_BARE_ASIN = re.compile(r"(?<![A-Za-z0-9_:])B0[0-9A-Z]{8}(?![A-Za-z0-9_])")
_NUM = r"\d+(?:[.,]\d+)*"
_ANY_NUMBER = re.compile(_NUM)
_PRICE = (re.compile(rf"\$\s?({_NUM})"), re.compile(rf"({_NUM})\s?(?:USD|usd|đô la|đô|dollars?)\b"))
_RATING = (re.compile(r"(?<![\d.,])(\d(?:[.,]\d)?)\s*/\s*5\b"), re.compile(r"(?<![\d.,])(\d(?:[.,]\d)?)\s*(?:sao|stars?)\b"))
_EPS = 1e-9


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
