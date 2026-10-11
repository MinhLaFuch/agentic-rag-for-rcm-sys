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


def _as_float(value: Any, name: str) -> float:
    """
    Convert value to float with proper error handling.

    Args:
        value: Value to convert
        name: Parameter name for error messages

    Returns:
        Float value

    Raises:
        ToolInputError: If value cannot be converted to float
    """
    try:
        return float(value)
    except (ValueError, TypeError) as exc:
        raise ToolInputError(
            f"{name} must be a number, got {type(value).__name__}: {value!r}"
        ) from exc


def _as_int(value: Any, name: str) -> int:
    """
    Convert value to int with proper error handling.

    Args:
        value: Value to convert
        name: Parameter name for error messages

    Returns:
        Integer value

    Raises:
        ToolInputError: If value cannot be converted to int
    """
    try:
        return int(value)
    except (ValueError, TypeError) as exc:
        raise ToolInputError(
            f"{name} must be an integer, got {type(value).__name__}: {value!r}"
        ) from exc


def compile_filters(
    filters: dict[str, Any],
    domains_known: set[str],
) -> tuple[str, list[Any], dict[str, Any]]:
    """
    Compile structured filters to parameterised SQL WHERE clause and params.

    Args:
        filters: Dictionary of filter conditions (same as SQLTool input_schema)
        domains_known: Set of valid domain names for validation

    Returns:
        Tuple of (WHERE clause string, list of parameter values, normalized filters)

    Raises:
        ToolInputError: If unknown filter keys or invalid domains are provided
    """
    clauses: list[str] = ["1=1"]
    params: list[Any] = []
    normalized: dict[str, Any] = {}

    if filters.get("domain") is not None:
        domains = _as_list(filters["domain"])
        if domains:  # Skip if empty (empty string or empty list = no filter)
            bad = [d for d in domains if d not in domains_known]
            if bad:
                raise ToolInputError(f"unknown domain(s) {bad}; available: {sorted(domains_known)}")
            clauses.append(f"domain IN ({','.join('?' * len(domains))})")
            params += domains
            normalized["domain"] = domains

    price_parts: list[str] = []
    price_min = filters.get("price_min")
    price_max = filters.get("price_max")
    if price_min is not None:
        price_min_float = _as_float(price_min, "price_min")
        price_parts.append("price >= ?")
        params.append(price_min_float)
        normalized["price_min"] = price_min_float
    if price_max is not None:
        price_max_float = _as_float(price_max, "price_max")
        price_parts.append("price <= ?")
        params.append(price_max_float)
        normalized["price_max"] = price_max_float
    if price_min is not None and price_max is not None and _as_float(price_min, "price_min") > _as_float(price_max, "price_max"):
        raise ToolInputError(
            f"price_min ({price_min}) > price_max ({price_max}). "
            "Swap the values or remove one of the filters."
        )
    if price_parts:
        clause = " AND ".join(price_parts)
        if filters.get("include_missing_price"):  # D-006 fallback: keep null-price items
            clause = f"(({clause}) OR price IS NULL)"
            normalized["include_missing_price"] = True
        clauses.append(clause)

    if filters.get("min_rating") is not None:
        min_rating = _as_float(filters["min_rating"], "min_rating")
        clauses.append("average_rating >= ?")
        params.append(min_rating)
        normalized["min_rating"] = min_rating
    if filters.get("min_rating_number") is not None:
        min_rating_number = _as_int(filters["min_rating_number"], "min_rating_number")
        clauses.append("rating_number >= ?")
        params.append(min_rating_number)
        normalized["min_rating_number"] = min_rating_number

    if filters.get("categories_any"):
        cats = _as_list(filters["categories_any"])
        if cats:
            clauses.append(
                "EXISTS (SELECT 1 FROM item_categories c WHERE c.item_id = items.item_id "
                f"AND c.category IN ({','.join('?' * len(cats))}))"
            )
            params += cats
            normalized["categories_any"] = cats
    if filters.get("categories_all"):
        cats = list(dict.fromkeys(_as_list(filters["categories_all"])))
        if cats:
            clauses.append(
                "(SELECT COUNT(DISTINCT c.category) FROM item_categories c WHERE "
                f"c.item_id = items.item_id AND c.category IN ({','.join('?' * len(cats))})) = ?"
            )
            params += cats + [len(cats)]
            normalized["categories_all"] = cats

    if filters.get("store"):
        stores = _as_list(filters["store"])
        if stores:
            # Case-insensitive comparison for better UX
            clauses.append(f"LOWER(store) IN ({','.join('?' * len(stores))})")
            params += [s.lower() for s in stores]
            normalized["store"] = stores

    if filters.get("title_contains"):
        title = str(filters["title_contains"])
        escaped = title.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        clauses.append("title LIKE ? ESCAPE '\\'")
        params.append(f"%{escaped}%")
        normalized["title_contains"] = title

    if filters.get("exclude_item_ids"):
        ex = _as_list(filters["exclude_item_ids"])
        if ex:
            clauses.append(f"item_id NOT IN ({','.join('?' * len(ex))})")
            params += ex
            normalized["exclude_item_ids"] = ex

    return " AND ".join(clauses), params, normalized
