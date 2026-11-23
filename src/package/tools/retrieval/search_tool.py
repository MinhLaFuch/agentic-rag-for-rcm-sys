"""
SearchTool: retrieve candidate items from free text (BM25 over item metadata).

Why this tool exists: SimilarTool / RankTool need user history, and ~72% of users
have a single interaction.  For those users the only signal is what they *say*
("quiet keyboard for coding under $50"), and FilterTool can only match structured
fields.  This tool turns text into candidates the rest of the pipeline can use.

"Semantic" is aspirational in this first version: it is lexical (SQLite FTS5 + BM25),
not embedding-based.  Measure candidate recall first; only add embeddings if
lexical recall on cold users is poor.  The interface stays the same either way.

Output candidates carry `item_id`, so they can be passed as-is to RankTool.
"""

from __future__ import annotations

from typing import Any
import re

import numpy as np

from ..base import Tool, ToolCallLogger, ToolInputError, check_top_k
from package.corpus import ItemCorpus
from ..sql import compile_filters
from .._limits import MAX_CANDIDATES, SEMANTIC_DEFAULT_LIMIT
from .._schema import FILTER_KEYS, ITEM_COLUMNS
from ._helper import _tokenize
from package.embeddings import VectorStore
from .indexed_bm25_rows import indexed_bm25_rows
from .vietnamese_query_translator import VietnameseQueryTranslator


class SearchTool(Tool):
    """
    Retrieve candidate items by free-text query (BM25 over title, store, main_category,
    categories).  Structured filters use the same keys as FilterTool, so the planner
    can combine "what the user said" with "hard constraints" in one call.
    """

    name = "SearchTool"
    description = (
        "Search items by keywords (BM25 over title, store, categories). "
        "Requires a text query; use FilterTool for purely structured filters without keywords. "
        "Pass ENGLISH keywords (the catalog is English): translate the user's request first. "
        "Categories must be exact names from the catalog (case-sensitive). "
        "Returns ranked candidates with a relevance score."
    )
    input_schema = {
        "query": "str  -- keywords, e.g. 'mechanical keyboard quiet'; English",
        "filters": {
            "domain": "str | list[str]  -- exact domain name; omit for all (empty string/list = no filter)",
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
        "limit": f"int (<= {MAX_CANDIDATES}, default {SEMANTIC_DEFAULT_LIMIT})",
    }
    output_schema = {
        "candidates": "list[{item_id, domain, title, store, price, ..., score}]  -- best match first",
        "total_matches": "int (None only when constructed with exact_count=False)", "query_tokens": "list[str]", "truncated": "bool", "applied_filters": "dict",
    }

    def __init__(self, corpus: ItemCorpus, logger: ToolCallLogger | None = None, *, exact_count: bool = True,
                 vector_store: VectorStore | None = None, query_encoder: Any | None = None,
                 rrf_k: int = 60, indexed_topk: bool = False, dense_search: Any | None = None,
                 fallback_to_bm25: bool = False, bm25_index: Any | None = None,
                 translate_vietnamese: bool = False) -> None:
        super().__init__(logger)
        if not isinstance(exact_count, bool):
            raise ValueError("exact_count must be boolean")
        self.exact_count = exact_count
        if not isinstance(indexed_topk, bool):
            raise ValueError('indexed_topk must be boolean')
        self.indexed_topk = indexed_topk
        if not isinstance(fallback_to_bm25, bool):
            raise ValueError("fallback_to_bm25 must be boolean")
        self.fallback_to_bm25 = fallback_to_bm25
        self.corpus = corpus
        if vector_store is not None and not isinstance(vector_store, VectorStore):
            raise TypeError("vector_store must be a VectorStore or None")
        if (vector_store is not None or dense_search is not None) and query_encoder is None:
            raise ValueError("query_encoder is required when vector_store or dense_search is configured")
        if isinstance(rrf_k, bool) or not isinstance(rrf_k, int) or rrf_k <= 0:
            raise ValueError("rrf_k must be a positive integer")
        self.vector_store = vector_store
        self.query_encoder = query_encoder
        self.dense_search = dense_search
        self.rrf_k = rrf_k
        self.bm25_index = bm25_index
        if not isinstance(translate_vietnamese, bool):
            raise ValueError("translate_vietnamese must be boolean")
        self.translate_vietnamese = translate_vietnamese
        self._vi_translator = VietnameseQueryTranslator() if translate_vietnamese else None
        if self.translate_vietnamese:
            self.description = (
                "Search items by Vietnamese or English query (Hybrid BM25 + Dense RRF over title, store, categories). "
                "Vietnamese shopping queries are automatically translated to English catalog keywords when needed. "
                "Use FilterTool for purely structured filters without text."
            )
        # Update domain filter with actual domain names for better documentation
        self.input_schema = {
            **type(self).input_schema,
            "filters": {
                **type(self).input_schema["filters"],
                "domain": f"str | list[str]  -- exact domain name, one of {corpus.domains()} (NOT a store name); omit for all (empty string/list = no filter)",
            }
        }

    def execute(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = SEMANTIC_DEFAULT_LIMIT,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            raise ToolInputError("`query` must be a non-empty string")
        limit = check_top_k(limit, name="limit")
        
        # Validate filters is a dictionary
        if filters is not None and not isinstance(filters, dict):
            raise ToolInputError(f"`filters` must be a dictionary, got {type(filters).__name__}")
        filters = filters or {}

        effective_query = query
        translation_info = None
        if self._vi_translator is not None:
            info = self._vi_translator.translate(query)
            if info["is_vietnamese"] and info["translated"]:
                effective_query = str(info["translated"])
                translation_info = info

        tokens = _tokenize(effective_query)
        if not tokens:
            raise ToolInputError(f"`query` has no searchable words after cleaning: {query!r}")

        # Same validation and parameterised compilation as FilterTool (unknown keys rejected).
        unknown = set(filters) - FILTER_KEYS
        if unknown:
            raise ToolInputError(f"unknown filter(s) {sorted(unknown)}; allowed: {sorted(FILTER_KEYS)}")
        where, params, normalized_filters = compile_filters(filters, set(self.corpus.domains()), corpus=self.corpus)
        # compile_filters is shared with single-table FilterTool queries and
        # emits bare column names. SearchTool joins items_fts, which duplicates
        # title/store columns; qualify only bare item columns here.
        where = re.sub(r"(?<![.\w])(domain|original_item_id|first_seen_ts|title|store|price|average_rating|rating_number|main_category)(?!\w)", r"items.\1", where)

        # Tokens are \w-only and double-quoted, so user text cannot inject FTS5 syntax.
        match = " OR ".join(f'"{t}"' for t in tokens)
        cols = ", ".join(f"items.{c}" for c in ITEM_COLUMNS)
        if self.bm25_index is not None:
            exclude_set = set(normalized_filters.get("exclude_item_ids") or [])
            rows = []
            fetch = max(limit * 4, 200)
            max_fetch = min(len(self.bm25_index), max(limit * 32, 4000))
            truncated = False
            while True:
                scored = self.bm25_index.search_with_scores(effective_query, seen=exclude_set, limit=fetch)
                if not scored:
                    break
                cand_ids = [iid for iid, _ in scored]
                score_map = {iid: sc for iid, sc in scored}
                found_meta: dict[str, dict[str, Any]] = {}
                for start in range(0, len(cand_ids), 500):
                    chunk = cand_ids[start:start + 500]
                    marks = ",".join("?" for _ in chunk)
                    chunk_sql = f"SELECT {cols} FROM items WHERE items.item_id IN ({marks}) AND {where}"
                    meta_rows, _ = self.corpus.select(chunk_sql, [*chunk, *params], max_rows=len(chunk))
                    for mr in meta_rows:
                        found_meta[mr["item_id"]] = mr
                rows = []
                for iid in cand_ids:
                    if iid in found_meta:
                        item_row = dict(found_meta[iid])
                        item_row["score"] = float(score_map[iid])
                        rows.append(item_row)
                if len(rows) >= limit or len(scored) < fetch or fetch >= max_fetch:
                    truncated = len(rows) > limit or len(scored) >= fetch
                    rows = rows[:limit]
                    break
                fetch = min(fetch * 2, max_fetch)
            total_matches = None if not self.exact_count else len(rows)
        else:
            # Secondary tie-breaker: rating_number DESC for equal BM25 scores
            sql = (
                f"SELECT {cols}, -bm25(items_fts) AS score "  # bm25() is lower-is-better -> negate
                f"FROM items_fts JOIN items ON items.rowid = items_fts.rowid "
                f"WHERE items_fts MATCH ? AND {where} "
                f"ORDER BY score DESC, items.rating_number DESC, items.item_id"
            )
            if self.indexed_topk:
                rows, truncated = indexed_bm25_rows(self.corpus, match, cols, where, params, limit)
            else:
                rows, truncated = self.corpus.select(sql, [match, *params], max_rows=limit)
            for r in rows:
                r["score"] = float(r["score"])

            # Count total matches using a subquery (corpus.count only works with items table)
            count_sql = (
                f"SELECT COUNT(*) AS cnt FROM items_fts JOIN items ON items.rowid = items_fts.rowid "
                f"WHERE items_fts MATCH ? AND {where}"
            )
            if self.exact_count:
                count_rows, _ = self.corpus.select(count_sql, [match, *params], max_rows=1)
                total_matches = count_rows[0]["cnt"] if count_rows else 0
            else:
                total_matches = None

        if self.vector_store is None and self.dense_search is None:
            out = {
                "candidates": rows,
                "total_matches": total_matches,
                "query_tokens": tokens,
                "truncated": truncated,
                "applied_filters": normalized_filters,
            }
            if translation_info is not None:
                out["translated_query"] = effective_query
            return out

        try:
            encoded = self.query_encoder.encode([effective_query]) if hasattr(self.query_encoder, "encode") else self.query_encoder([effective_query])
            query_vec = np.asarray(encoded, dtype=np.float32)
            if query_vec.ndim == 2:
                query_vec = query_vec[0]
            if query_vec.ndim != 1 or not np.all(np.isfinite(query_vec)) or float(np.linalg.norm(query_vec)) <= 0.0:
                raise RuntimeError("query encoder returned invalid vector")
            fetch_k = max(limit * 2, limit)
            max_fetch = max(fetch_k, min(4000, limit * 32))
            metadata = {}
            while True:
                if self.dense_search is not None:
                    raw_dense = self.dense_search(query_vec, fetch_k)
                    dense_ids = [r[0] if isinstance(r, tuple) else str(r) for r in raw_dense]
                    dense_backend = "ann"
                else:
                    dense_rows = self.vector_store.search(query_vec, fetch_k)
                    dense_ids = [item_id for item_id, _ in dense_rows]
                    dense_backend = "exact"
                dense_ids = list(dict.fromkeys(dense_ids))
                for start in range(0, len(dense_ids), 500):
                    chunk = dense_ids[start:start + 500]
                    placeholders = ",".join("?" for _ in chunk)
                    dense_sql = f"SELECT {cols} FROM items WHERE items.item_id IN ({placeholders}) AND {where}"
                    dense_meta, _ = self.corpus.select(dense_sql, [*chunk, *params], max_rows=len(chunk))
                    metadata.update({row["item_id"]: row for row in dense_meta})
                surviving_ids = [iid for iid in dense_ids if iid in metadata]
                if len(surviving_ids) >= limit or len(dense_ids) < fetch_k or fetch_k >= max_fetch:
                    dense_fetch_limited = len(surviving_ids) < limit and len(dense_ids) >= fetch_k
                    dense_ids = surviving_ids
                    break
                fetch_k = min(fetch_k * 2, max_fetch)
        except Exception as exc:
            if self.fallback_to_bm25:
                out = {
                    "candidates": rows,
                    "total_matches": total_matches,
                    "query_tokens": tokens,
                    "truncated": truncated,
                    "applied_filters": normalized_filters,
                    "retrieval": "bm25_fallback",
                    "fallback_reason": f"{type(exc).__name__}: {exc}",
                    "dense_candidates": 0,
                }
                if translation_info is not None:
                    out["translated_query"] = effective_query
                return out
            raise
        lexical_rank = {row["item_id"]: rank for rank, row in enumerate(rows, 1)}
        dense_rank = {item_id: rank for rank, item_id in enumerate(dense_ids, 1)}
        union = set(lexical_rank) | set(dense_rank)
        def fused_score(item_id):
            return ((1 / (self.rrf_k + lexical_rank[item_id])) if item_id in lexical_rank else 0.0) + \
                   ((1 / (self.rrf_k + dense_rank[item_id])) if item_id in dense_rank else 0.0)
        fused = sorted(union, key=lambda item_id: (-fused_score(item_id), item_id))[:limit]
        lexical_meta = {row["item_id"]: row for row in rows}
        candidates = []
        for item_id in fused:
            row = dict(lexical_meta.get(item_id) or metadata[item_id])
            row["score"] = float(fused_score(item_id))
            row["retrieval_sources"] = [source for source, ranks in (("bm25", lexical_rank), ("dense", dense_rank)) if item_id in ranks]
            candidates.append(row)
        out = {
            "candidates": candidates,
            "total_matches": total_matches,
            "query_tokens": tokens,
            "truncated": truncated,
            "applied_filters": normalized_filters,
            "retrieval": "rrf",
            "dense_backend": dense_backend,
            "dense_candidates": len(dense_ids),
            "dense_fetch_k": fetch_k,
            "dense_fetch_limited": dense_fetch_limited,
        }
        if translation_info is not None:
            out["translated_query"] = effective_query
        return out
