"""Helper functions for sql_query module."""

from __future__ import annotations

from typing import Any

from .._schema import FILTER_KEYS
from ..base import ToolInputError


def _as_list(value: Any) -> list[Any]:
    """
    Convert value to list.

    Empty list/string handling rule:
    - Empty string ("" or whitespace-only) -> [] (treated as 'no filter')
    - Empty list -> [] (treated as 'no filter')
    - Single value -> [value]
    - List/tuple/set -> list(value)

    This ensures consistency across all filter fields that accept lists.
    """
    if isinstance(value, str):
        return [] if not value.strip() else [value]
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def compile_filters(
    filters: dict[str, Any],
    domains_known: set[str],
) -> tuple[str, list[Any]]:
    """
    Compile structured filters to parameterised SQL WHERE clause and params.

    Args:
        filters: Dictionary of filter conditions (same as SQLTool input_schema)
        domains_known: Set of valid domain names for validation

    Returns:
        Tuple of (WHERE clause string, list of parameter values)

    Raises:
        ToolInputError: If unknown filter keys or invalid domains are provided
    """
    clauses: list[str] = ["1=1"]
    params: list[Any] = []

    if filters.get("domain") is not None:
        domains = _as_list(filters["domain"])
        if domains:  # Skip if empty (empty string or empty list = no filter)
            bad = [d for d in domains if d not in domains_known]
            if bad:
                raise ToolInputError(f"unknown domain(s) {bad}; available: {sorted(domains_known)}")
            clauses.append(f"domain IN ({','.join('?' * len(domains))})")
            params += domains

    price_parts: list[str] = []
    price_min = filters.get("price_min")
    price_max = filters.get("price_max")
    if price_min is not None:
        price_parts.append("price >= ?")
        params.append(float(price_min))
    if price_max is not None:
        price_parts.append("price <= ?")
        params.append(float(price_max))
    if price_min is not None and price_max is not None and float(price_min) > float(price_max):
        raise ToolInputError(
            f"price_min ({price_min}) > price_max ({price_max}). "
            "Swap the values or remove one of the filters."
        )
    if price_parts:
        clause = " AND ".join(price_parts)
        if filters.get("include_missing_price"):  # D-006 fallback: keep null-price items
            clause = f"(({clause}) OR price IS NULL)"
        clauses.append(clause)

    if filters.get("min_rating") is not None:
        clauses.append("average_rating >= ?")
        params.append(float(filters["min_rating"]))
    if filters.get("min_rating_number") is not None:
        clauses.append("rating_number >= ?")
        params.append(int(filters["min_rating_number"]))

    if filters.get("categories_any"):
        cats = _as_list(filters["categories_any"])
        if cats:
            clauses.append(
                "EXISTS (SELECT 1 FROM item_categories c WHERE c.item_id = items.item_id "
                f"AND c.category IN ({','.join('?' * len(cats))}))"
            )
            params += cats
    if filters.get("categories_all"):
        cats = list(dict.fromkeys(_as_list(filters["categories_all"])))
        if cats:
            clauses.append(
                "(SELECT COUNT(DISTINCT c.category) FROM item_categories c WHERE "
                f"c.item_id = items.item_id AND c.category IN ({','.join('?' * len(cats))})) = ?"
            )
            params += cats + [len(cats)]

    if filters.get("store"):
        stores = _as_list(filters["store"])
        if stores:
            # Case-insensitive comparison for better UX
            clauses.append(f"LOWER(store) IN ({','.join('?' * len(stores))})")
            params += [s.lower() for s in stores]

    if filters.get("title_contains"):
        escaped = str(filters["title_contains"]).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        clauses.append("title LIKE ? ESCAPE '\\'")
        params.append(f"%{escaped}%")

    if filters.get("exclude_item_ids"):
        ex = _as_list(filters["exclude_item_ids"])
        clauses.append(f"item_id NOT IN ({','.join('?' * len(ex))})")
        params += ex

    return " AND ".join(clauses), params
