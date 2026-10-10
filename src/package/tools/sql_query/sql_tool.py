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
from .._limits import MAX_CANDIDATES, SQL_DEFAULT_LIMIT
from .._schema import FILTER_KEYS, ITEM_COLUMNS, ORDER_COLUMNS
from ._helper import _as_list, compile_filters

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
            "domain": "str | list[str]  -- omit for all domains (empty string/list = no filter)",
            "price_min / price_max": "float  -- excludes null-price items unless include_missing_price=true",
            "include_missing_price": "bool (default false)",
            "min_rating": "float",
            "min_rating_number": "int",
            "categories_any": "list[str]  -- item has at least one (empty list = no filter)",
            "categories_all": "list[str]  -- item has all (empty list = no filter)",
            "store": "str | list[str]  -- case-insensitive match (empty string/list = no filter)",
            "title_contains": "str",
            "exclude_item_ids": "list[str]",
        },
        "order_by": "rating_number | average_rating | price (default rating_number)",
        "descending": "bool (default true)",
        "limit": f"int (<= {MAX_CANDIDATES}, default {SQL_DEFAULT_LIMIT})",
    }
    output_schema = {
        "candidates": "list[{item_id, domain, title, store, price, ...}]",
        "total_matches": "int", "truncated": "bool", "applied_filters": "dict",
    }

    def __init__(self, corpus: ItemCorpus, logger: ToolCallLogger | None = None) -> None:
        super().__init__(logger)
        self.corpus = corpus

    def execute(
        self,
        filters: dict[str, Any] | None = None,
        order_by: str = "rating_number",
        descending: bool = True,
        limit: int = SQL_DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        filters = filters or {}
        unknown = set(filters) - FILTER_KEYS
        if unknown:
            raise ToolInputError(f"unknown filter(s) {sorted(unknown)}; allowed: {sorted(FILTER_KEYS)}")
        if order_by not in ORDER_COLUMNS:
            raise ToolInputError(f"order_by must be one of {sorted(ORDER_COLUMNS)}")
        limit = check_top_k(limit)

        where, params = compile_filters(filters, set(self.corpus.domains()))
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
