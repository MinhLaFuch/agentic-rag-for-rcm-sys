"""
SemanticSearchTool: retrieve candidate items from free text (BM25 over item metadata).

Why this tool exists: ItemCFTool / RecoModelTool need user history, and ~72% of users
have a single interaction.  For those users the only signal is what they *say*
("quiet keyboard for coding under $50"), and SQLTool can only match structured
fields.  This tool turns text into candidates the rest of the pipeline can use.

"Semantic" is aspirational in this first version: it is lexical (SQLite FTS5 + BM25),
not embedding-based.  Measure candidate recall first; only add embeddings if
lexical recall on cold users is poor.  The interface stays the same either way.

Output candidates carry `item_id`, so they can be passed as-is to RecoModelTool.
"""

from __future__ import annotations

from typing import Any

from ..base import Tool, ToolCallLogger, ToolInputError, check_top_k
from ..corpus import ItemCorpus
from ..sql_query.sql_tool import SQLTool
from .._config import FILTER_KEYS, ITEM_COLUMNS, MAX_CANDIDATES
from ._config import DEFAULT_LIMIT, MAX_QUERY_TOKENS
from ._helper import _tokenize


class SemanticSearchTool(Tool):
    """
    Retrieve candidate items by free-text query (BM25 over title, store, main_category,
    categories).  Structured filters use the same keys as SQLTool, so the planner
    can combine "what the user said" with "hard constraints" in one call.
    """

    name = "SemanticSearchTool"
    description = (
        "Search items by keywords. Pass ENGLISH keywords (the catalog is English): "
        "translate the user's request first. Returns ranked candidates with a relevance score."
    )
    input_schema = {
        "query": "str  -- keywords, e.g. 'mechanical keyboard quiet'; English",
        "filters": "dict | None  -- same keys as SQLTool.filters (domain, price_max, min_rating, ...)",
        "limit": f"int (<= {MAX_CANDIDATES}, default {DEFAULT_LIMIT})",
    }

    def __init__(self, corpus: ItemCorpus, logger: ToolCallLogger | None = None) -> None:
        super().__init__(logger)
        self.corpus = corpus
        self._sql = SQLTool(corpus)  # reused only for its filter compiler

    def execute(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            raise ToolInputError("`query` must be a non-empty string")
        limit = check_top_k(limit)
        filters = filters or {}

        tokens = _tokenize(query)
        if not tokens:
            raise ToolInputError(f"`query` has no searchable words after cleaning: {query!r}")

        # Same validation and parameterised compilation as SQLTool (unknown keys rejected).
        unknown = set(filters) - FILTER_KEYS
        if unknown:
            raise ToolInputError(f"unknown filter(s) {sorted(unknown)}; allowed: {sorted(FILTER_KEYS)}")
        where, params = self._sql._compile(filters)

        # Tokens are \w-only and double-quoted, so user text cannot inject FTS5 syntax.
        match = " OR ".join(f'"{t}"' for t in tokens)
        cols = ", ".join(f"items.{c}" for c in ITEM_COLUMNS)
        sql = (
            f"SELECT {cols}, -bm25(items_fts) AS score "  # bm25() is lower-is-better -> negate
            f"FROM items_fts JOIN items ON items.rowid = items_fts.rowid "
            f"WHERE items_fts MATCH ? AND {where} "
            f"ORDER BY score DESC, items.item_id"
        )
        rows, truncated = self.corpus.select(sql, [match, *params], max_rows=limit)
        for r in rows:
            r["score"] = round(float(r["score"]), 4)
        return {
            "candidates": rows,
            "query_tokens": tokens,
            "truncated": truncated,
            "applied_filters": filters,
        }
