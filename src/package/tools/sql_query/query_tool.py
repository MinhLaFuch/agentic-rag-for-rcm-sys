"""QueryTool: ask the corpus for item information (by ids or one read-only SELECT)."""

from __future__ import annotations

from typing import Any, Sequence

from ..base import Tool, ToolCallLogger, ToolInputError, check_top_k
from ..corpus import ItemCorpus
from .._limits import MAX_QUERY_ROWS, QUERY_DEFAULT_MAX_ROWS
from .._schema import ITEM_COLUMNS, SCHEMA_HINT


class QueryTool(Tool):
    """Ask the corpus for item information: by item ids, or by a raw read-only SELECT."""

    name = "QueryTool"
    description = (
        "Look up item information. Provide either `item_ids` (namespaced) or a single "
        f"read-only `query` (SELECT). Tables: {SCHEMA_HINT}. Results are capped at {MAX_QUERY_ROWS} rows."
    )
    input_schema = {
        "query": "str | None  -- one SELECT statement",
        "item_ids": "list[str] | None  -- namespaced item ids",
        "max_rows": f"int (<= {MAX_QUERY_ROWS}, default {QUERY_DEFAULT_MAX_ROWS})",
    }
    output_schema = {
        "items": "list[{item_id, domain, title, store, price, average_rating, rating_number, main_category}]",
        "missing_item_ids": "list[str]  -- only with item_ids", "truncated": "bool",
    }

    def __init__(self, corpus: ItemCorpus, logger: ToolCallLogger | None = None) -> None:
        super().__init__(logger)
        self.corpus = corpus

    def execute(
        self,
        query: str | None = None,
        item_ids: Sequence[str] | None = None,
        max_rows: int = QUERY_DEFAULT_MAX_ROWS,
    ) -> dict[str, Any]:
        if (query is None) == (item_ids is None):
            raise ToolInputError("provide exactly one of `query` or `item_ids`")
        max_rows = check_top_k(max_rows, MAX_QUERY_ROWS)

        if item_ids is not None:
            ids = list(dict.fromkeys(item_ids))
            if not ids:
                raise ToolInputError("`item_ids` is empty")
            if len(ids) > MAX_QUERY_ROWS:
                raise ToolInputError(f"at most {MAX_QUERY_ROWS} item_ids per call")
            marks = ",".join("?" * len(ids))
            cols = ", ".join(ITEM_COLUMNS)
            # For item_ids, fetch all matching items first (capped by internal limit)
            rows, _ = self.corpus.select(
                f"SELECT {cols} FROM items WHERE item_id IN ({marks})", ids, max_rows=len(ids)
            )
            # Preserve input order by re-sorting
            found_map = {r["item_id"]: r for r in rows}
            ordered_rows = [found_map[i] for i in ids if i in found_map]
            # Apply max_rows to respect user's limit
            truncated = len(ordered_rows) > max_rows
            ordered_rows = ordered_rows[:max_rows]
            found = set(found_map.keys())
            return {
                "items": ordered_rows,
                "missing_item_ids": [i for i in ids if i not in found],
                "truncated": truncated,
            }

        rows, truncated = self.corpus.select(query, max_rows=max_rows)
        return {"items": rows, "missing_item_ids": [], "truncated": truncated}
