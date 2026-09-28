"""
SQLTool: retrieve candidate items with structured conditions.

Filters are compiled to parameterised SQL (no string interpolation of user
values), so the LLM cannot inject SQL through this tool; use QueryTool for
free-form SELECTs.
"""

from __future__ import annotations

from typing import Any

from ..base import Tool, ToolCallLogger, ToolInputError, check_top_k
from ..corpus import ItemCorpus
from .._config import *

class SQLTool(Tool):
    """
    Retrieve candidate items with structured conditions.  Filters are compiled to
    parameterised SQL (no string interpolation of user values), so the LLM can
    never inject SQL through this tool; use QueryTool for free-form SELECTs.
    """

    name = "SQLTool"
    description = (
        "Retrieve candidate items with structured filters. Unknown filter keys are rejected."
    )
    input_schema = {
        "filters": {
            "domain": "str | list[str]  -- omit for all domains",
            "price_min / price_max": "float  -- excludes null-price items unless include_missing_price=true",
            "include_missing_price": "bool (default false)",
            "min_rating": "float",
            "min_rating_number": "int",
            "categories_any": "list[str]  -- item has at least one",
            "categories_all": "list[str]  -- item has all",
            "store": "str | list[str]",
            "title_contains": "str",
            "exclude_item_ids": "list[str]",
        },
        "order_by": "rating_number | average_rating | price (default rating_number)",
        "descending": "bool (default true)",
        "limit": f"int (<= {MAX_CANDIDATES}, default 100)",
    }

    def __init__(self, corpus: ItemCorpus, logger: ToolCallLogger | None = None) -> None:
        super().__init__(logger)
        self.corpus = corpus

    def execute(
        self,
        filters: dict[str, Any] | None = None,
        order_by: str = "rating_number",
        descending: bool = True,
        limit: int = 100,
    ) -> dict[str, Any]:
        filters = filters or {}
        unknown = set(filters) - _FILTER_KEYS
        if unknown:
            raise ToolInputError(f"unknown filter(s) {sorted(unknown)}; allowed: {sorted(_FILTER_KEYS)}")
        if order_by not in _ORDER_COLUMNS:
            raise ToolInputError(f"order_by must be one of {sorted(_ORDER_COLUMNS)}")
        limit = check_top_k(limit)

        where, params = self._compile(filters)
        direction = "DESC" if descending else "ASC"
        cols = ", ".join(ITEM_COLUMNS)
        # NULLs last, then item_id so results are deterministic
        sql = (
            f"SELECT {cols} FROM items WHERE {where} "
            f"ORDER BY {order_by} IS NULL, {order_by} {direction}, item_id"
        )
        rows, truncated = self.corpus.select(sql, params, max_rows=limit)
        return {
            "candidates": rows,
            "total_matches": self.corpus.count(where, params),
            "truncated": truncated,
            "applied_filters": filters,
        }

    def _compile(self, f: dict[str, Any]) -> tuple[str, list[Any]]:
        clauses: list[str] = ["1=1"]
        params: list[Any] = []

        if f.get("domain") is not None:
            domains = _as_list(f["domain"])
            known = set(self.corpus.domains())
            bad = [d for d in domains if d not in known]
            if bad:
                raise ToolInputError(f"unknown domain(s) {bad}; available: {sorted(known)}")
            clauses.append(f"domain IN ({','.join('?' * len(domains))})")
            params += domains

        price_parts: list[str] = []
        if f.get("price_min") is not None:
            price_parts.append("price >= ?")
            params.append(float(f["price_min"]))
        if f.get("price_max") is not None:
            price_parts.append("price <= ?")
            params.append(float(f["price_max"]))
        if price_parts:
            clause = " AND ".join(price_parts)
            if f.get("include_missing_price"):  # D-006 fallback: keep null-price items
                clause = f"(({clause}) OR price IS NULL)"
            clauses.append(clause)

        if f.get("min_rating") is not None:
            clauses.append("average_rating >= ?")
            params.append(float(f["min_rating"]))
        if f.get("min_rating_number") is not None:
            clauses.append("rating_number >= ?")
            params.append(int(f["min_rating_number"]))

        if f.get("categories_any"):
            cats = _as_list(f["categories_any"])
            clauses.append(
                "EXISTS (SELECT 1 FROM item_categories c WHERE c.item_id = items.item_id "
                f"AND c.category IN ({','.join('?' * len(cats))}))"
            )
            params += cats
        if f.get("categories_all"):
            cats = list(dict.fromkeys(_as_list(f["categories_all"])))
            clauses.append(
                "(SELECT COUNT(DISTINCT c.category) FROM item_categories c WHERE "
                f"c.item_id = items.item_id AND c.category IN ({','.join('?' * len(cats))})) = ?"
            )
            params += cats + [len(cats)]

        if f.get("store"):
            stores = _as_list(f["store"])
            clauses.append(f"store IN ({','.join('?' * len(stores))})")
            params += stores

        if f.get("title_contains"):
            escaped = str(f["title_contains"]).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            clauses.append("title LIKE ? ESCAPE '\\'")
            params.append(f"%{escaped}%")

        if f.get("exclude_item_ids"):
            ex = _as_list(f["exclude_item_ids"])
            clauses.append(f"item_id NOT IN ({','.join('?' * len(ex))})")
            params += ex

        return " AND ".join(clauses), params


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple, set)) else [value]
