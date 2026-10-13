"""Helper functions for sql_query module."""

from __future__ import annotations

import math
from typing import Any

from .._schema import FILTER_KEYS
from ..base import ToolInputError


def _as_list(value: Any, name: str = "value", allow_none: bool = False) -> list[Any]:
    """
    Convert value to list.

    Empty list/string handling rule:
    - Empty string ("" or whitespace-only) -> [] (treated as 'no filter')
    - Empty list -> [] (treated as 'no filter')
    - Single value -> [value]
    - List/tuple/set -> list(value)

    Args:
        value: Value to convert
        name: Parameter name for error messages
        allow_none: Whether None values in the list are allowed

    Returns:
        List of values

    Raises:
        ToolInputError: If None values are present and not allowed
    """
    if isinstance(value, str):
        return [] if not value.strip() else [value]
    if isinstance(value, (list, tuple, set)):
        result = list(value)
        if not allow_none and None in result:
            raise ToolInputError(
                f"{name} cannot contain None values"
            )
        return result
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
        ToolInputError: If value cannot be converted to float, is NaN/infinite, or is a boolean
    """
    # Reject booleans explicitly (bool is a subclass of int in Python)
    if isinstance(value, bool):
        raise ToolInputError(
            f"{name} must be a number, got boolean: {value!r}"
        )
    try:
        f = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ToolInputError(
            f"{name} must be a number, got {type(value).__name__}: {value!r}"
        ) from exc
    if math.isnan(f) or math.isinf(f):
        raise ToolInputError(
            f"{name} must be a finite number, got {f!r}"
        )
    return f


def _as_int(value: Any, name: str) -> int:
    """
    Convert value to int with proper error handling.

    Args:
        value: Value to convert
        name: Parameter name for error messages

    Returns:
        Integer value

    Raises:
        ToolInputError: If value cannot be converted to int or is not a true integer
    """
    # Reject booleans explicitly (bool is a subclass of int in Python)
    if isinstance(value, bool):
        raise ToolInputError(
            f"{name} must be an integer, got boolean: {value!r}"
        )
    try:
        f = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ToolInputError(
            f"{name} must be an integer, got {type(value).__name__}: {value!r}"
        ) from exc
    if math.isnan(f) or math.isinf(f):
        raise ToolInputError(
            f"{name} must be a finite integer, got {f!r}"
        )
    if f != int(f):
        raise ToolInputError(
            f"{name} must be an integer, got {type(value).__name__}: {value!r}"
        )
    return int(f)


def _ascii_lower(text: str) -> str:
    """Lower-case ASCII letters only: exactly what SQLite's LOWER() does. Python's str.lower() also folds
    non-ASCII letters (e.g. 'Ü' -> 'ü') which SQLite leaves alone, so the two sides would never match."""
    return text.translate(_ASCII_LOWER)


_ASCII_LOWER = {c: c + 32 for c in range(ord("A"), ord("Z") + 1)}


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
        domains = _as_list(filters["domain"], "domain")
        if domains:  # Skip if empty (empty string or empty list = no filter)
            # Validate all domain values are strings
            non_string = [d for d in domains if not isinstance(d, str)]
            if non_string:
                raise ToolInputError(
                    f"domain must be string(s), got non-string values: {non_string}"
                )
            bad = [d for d in domains if d not in domains_known]
            if bad:
                raise ToolInputError(f"unknown domain(s) {bad}; available: {sorted(domains_known)}")
            clauses.append(f"domain IN ({','.join('?' * len(domains))})")
            params += domains
            normalized["domain"] = domains

    include_missing_price = filters.get("include_missing_price")
    if include_missing_price is not None and not isinstance(include_missing_price, bool):
        raise ToolInputError(
            f"include_missing_price must be a boolean (true/false), got {include_missing_price!r}"
        )

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
        if include_missing_price:  # D-006 fallback: keep null-price items
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
        cats = _as_list(filters["categories_any"], "categories_any")
        if cats:
            # Validate all category values are strings
            non_string = [c for c in cats if not isinstance(c, str)]
            if non_string:
                raise ToolInputError(
                    f"categories_any must be string(s), got non-string values: {non_string}"
                )
            clauses.append(
                "EXISTS (SELECT 1 FROM item_categories c WHERE c.item_id = items.item_id "
                f"AND c.category IN ({','.join('?' * len(cats))}))"
            )
            params += cats
            normalized["categories_any"] = cats
    if filters.get("categories_all"):
        cats = list(dict.fromkeys(_as_list(filters["categories_all"], "categories_all")))
        if cats:
            # Validate all category values are strings
            non_string = [c for c in cats if not isinstance(c, str)]
            if non_string:
                raise ToolInputError(
                    f"categories_all must be string(s), got non-string values: {non_string}"
                )
            clauses.append(
                "(SELECT COUNT(DISTINCT c.category) FROM item_categories c WHERE "
                f"c.item_id = items.item_id AND c.category IN ({','.join('?' * len(cats))})) = ?"
            )
            params += cats + [len(cats)]
            normalized["categories_all"] = cats

    if filters.get("store"):
        stores = _as_list(filters["store"], "store")
        if stores:
            # Validate all store values are strings
            non_string = [s for s in stores if not isinstance(s, str)]
            if non_string:
                raise ToolInputError(
                    f"store must be string(s), got non-string values: {non_string}"
                )
            # Case-insensitive for ASCII letters (SQLite LOWER() semantics); other letters match exactly
            clauses.append(f"LOWER(store) IN ({','.join('?' * len(stores))})")
            params += [_ascii_lower(s) for s in stores]
            normalized["store"] = stores

    if filters.get("title_contains"):
        title = filters["title_contains"]
        if not isinstance(title, str):
            raise ToolInputError(
                f"title_contains must be a string, got {type(title).__name__}: {title!r}"
            )
        # Reject null character which can truncate LIKE pattern in SQLite
        if "\x00" in title:
            raise ToolInputError(
                f"title_contains cannot contain null character (\\x00)"
            )
        escaped = title.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        clauses.append("title LIKE ? ESCAPE '\\'")
        params.append(f"%{escaped}%")
        normalized["title_contains"] = title

    if filters.get("exclude_item_ids"):
        ex = _as_list(filters["exclude_item_ids"], "exclude_item_ids")
        if ex:
            # Validate all item_id values are strings
            non_string = [e for e in ex if not isinstance(e, str)]
            if non_string:
                raise ToolInputError(
                    f"exclude_item_ids must be string(s), got non-string values: {non_string}"
                )
            clauses.append(f"item_id NOT IN ({','.join('?' * len(ex))})")
            params += ex
            normalized["exclude_item_ids"] = ex

    return " AND ".join(clauses), params, normalized
