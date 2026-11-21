"""
FilterTool: retrieve candidate items with structured conditions.

Filters are compiled to parameterised SQL (no string interpolation of user
values), so the LLM cannot inject SQL through this tool; use LookupTool for
free-form SELECTs.
"""

from __future__ import annotations

from typing import Any

from ..base import Tool, ToolCallLogger, ToolInputError, check_top_k
from package.corpus import ItemCorpus
from .._limits import MAX_CANDIDATES, SQL_DEFAULT_LIMIT
from .._schema import FILTER_KEYS, ITEM_COLUMNS, ORDER_COLUMNS
from .compile_filters import compile_filters

class FilterTool(Tool):
    """
    Retrieve candidate items with structured conditions.  Filters are compiled to
    parameterised SQL (no string interpolation of user values), so the LLM can
    never inject SQL through this tool; use LookupTool for free-form SELECTs.
    """

    name = "FilterTool"
    description = (
        "Retrieve candidate items with structured filters (domain, category, price, rating, store). "
        "Does not require a text query; use SearchTool for keyword-based retrieval. "
        "Categories must be exact names from the catalog (case-sensitive). Unknown filter keys are rejected."
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
        "order_by": "rating_number | average_rating | price | popularity (default rating_number; "
                    "masked fields fall back to popularity when available)",
        "descending": "bool (default true)",
        "limit": f"int (<= {MAX_CANDIDATES}, default {SQL_DEFAULT_LIMIT})",
    }
    output_schema = {
        "candidates": "list[{item_id, domain, title, store, price, ...}]",
        "total_matches": "int",
        "truncated": "bool",
        "applied_filters": "dict  -- normalized filters with validated types",
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
        **kwargs: Any,
    ) -> dict[str, Any]:
        # Validate filters is a dictionary
        if filters is not None and not isinstance(filters, dict):
            raise ToolInputError(f"`filters` must be a dictionary, got {type(filters).__name__}")
        filters = filters or {}
        unknown = set(filters) - FILTER_KEYS
        if unknown:
            raise ToolInputError(f"unknown filter(s) {sorted(unknown)}; allowed: {sorted(FILTER_KEYS)}")
        if order_by not in ORDER_COLUMNS:
            raise ToolInputError(f"order_by must be one of {sorted(ORDER_COLUMNS)}")
        if not isinstance(descending, bool):  # the string "false" is truthy: it would silently sort DESC
            raise ToolInputError(f"`descending` must be a boolean (true/false), got {descending!r}")
        limit = check_top_k(limit, name="limit")

        where, params, normalized = compile_filters(filters, set(self.corpus.domains()), corpus=self.corpus)

        # Metadata policy may mask mutable fields (price/average_rating/
        # rating_number -> NULL). Constraints on masked fields silently match
        # nothing; ordering by them degenerates to item_id order. Fail loudly
        # for filters, and fall back to the causal `popularity` proxy for
        # ordering when the policy exposed it.
        policy = getattr(self.corpus, "_evaluation_metadata_policy", None) or {}
        masked = set(policy.get("masked_fields") or ())
        policy_name = policy.get("name")
        if masked:
            blocked = sorted(
                f for f in normalized
                if {"price_min": "price", "price_max": "price",
                    "include_missing_price": "price",
                    "min_rating": "average_rating",
                    "min_rating_number": "rating_number"}.get(f) in masked
            )
            if blocked:
                raise ToolInputError(
                    f"filter(s) {blocked} target masked field(s) under metadata policy "
                    f"'{policy_name}' (mutable fields are hidden to prevent future "
                    "leakage, so these constraints cannot be evaluated). Drop them "
                    "or use domain/categories/store/title_contains instead."
                )
        order_by_effective = order_by
        order_by_note = None
        degenerate_order = False
        if order_by in masked:
            if policy.get("popularity_available"):
                order_by_effective = "popularity"
                order_by_note = (
                    f"order_by '{order_by}' is masked under '{policy_name}'; "
                    "using causal popularity proxy (fit-split interaction count)"
                )
            else:
                # No causal proxy available: keep the old deterministic
                # item_id ordering rather than failing every FilterTool call,
                # but surface it so the planner/eval logs show the degradation.
                order_by_effective = "item_id"
                degenerate_order = True
                order_by_note = (
                    f"order_by '{order_by}' is masked under '{policy_name}' and "
                    "no popularity proxy is available; results are in item_id "
                    "order (effectively unordered by popularity)"
                )

        direction = "DESC" if descending else "ASC"
        cols = ", ".join(ITEM_COLUMNS)
        if order_by_effective == "popularity":
            if not policy.get("popularity_available"):
                raise ToolInputError(
                    "order_by='popularity' requires the evaluation metadata "
                    "policy to expose fit-split interaction counts; unavailable "
                    f"under '{policy_name}'."
                )
            # Drive from the item_popularity index (cnt, item_id) and probe the
            # items view per row — ORDER BY over the 2M-row view would need a
            # full sort (~24s) and always blow the SQL time budget. CROSS JOIN
            # pins the join order so the index scan + early LIMIT applies.
            sql = (
                f"SELECT {', '.join('items.' + c for c in ITEM_COLUMNS)} "
                "FROM (SELECT item_id AS pid, cnt FROM item_popularity "
                f"ORDER BY cnt {direction}, item_id) AS p "
                "CROSS JOIN items ON p.pid = items.item_id "
                f"WHERE {where} "
                f"ORDER BY p.cnt {direction}, p.pid"
            )
        elif degenerate_order:
            sql = f"SELECT {cols} FROM items WHERE {where} ORDER BY item_id"
        else:
            # NULLs last, then item_id so results are deterministic
            sql = (
                f"SELECT {cols} FROM items WHERE {where} "
                f"ORDER BY {order_by_effective} IS NULL, {order_by_effective} {direction}, item_id"
            )
        rows, truncated = self.corpus.select(sql, params, max_rows=limit)
        out = {
            "candidates": rows,
            "total_matches": self.corpus.count(where, params),
            "truncated": truncated,
            "applied_filters": normalized,
        }
        if order_by_effective != order_by:
            out["order_by_effective"] = order_by_effective
            out["order_by_note"] = order_by_note
        return out
