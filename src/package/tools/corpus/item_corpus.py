"""
Read-only item store shared by QueryTool, SQLTool, SemanticSearchTool, and MemoryTool
(also used by ItemCFTool and RecoModelTool to attach domain).

Built once from a metadata DataFrame, then locked: `query_only` pragma plus an
authoriser that only allows SELECT.  Item ids are namespaced "{domain}::{parent_asin}";
the domain is stored as a column and looked up directly from the database.

Three tables:
  - items: main item metadata (item_id, domain, title, price, ratings, etc.)
  - item_categories: multi-label categories (one row per item-category pair)
  - items_fts: FTS5 full-text search index over title, store, main_category, and categories
"""

from __future__ import annotations

import difflib
import sqlite3
import time
import warnings
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from ...data import ITEM_ID_SEPARATOR, namespaced_item_id
from ..base import ToolInputError
from .._limits import MAX_QUERY_ROWS, SQL_TIME_BUDGET_SECONDS
from .._schema import ITEM_COLUMNS, SCHEMA_HINT
from ._error import SQLTimeOutError
from ._helper import _clean_row, normalize_categories, numeric_column, read_only_authorizer
from ._schema import QUERY_CHUNK_SIZE
from ._sql import (
    CATEGORIES_INDEXES,
    CATEGORIES_TABLE_SCHEMA,
    FTS_POPULATE_SQL,
    FTS_TABLE_SCHEMA,
    ITEMS_TABLE_SCHEMA,
    ITEMS_INDEXES,
)



class ItemCorpus:
    """
    Read-only item store. Built once from a metadata DataFrame, then locked:
    query_only pragma + an authoriser that only allows SELECT, so tools cannot
    modify or exfiltrate anything beyond reading.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.execute("PRAGMA query_only = ON")
        self._conn.set_authorizer(read_only_authorizer())

    # ---- construction ---------------------------------------------------- #

    @classmethod
    def from_dataframe(cls, meta: pd.DataFrame, domain: str | None = None) -> "ItemCorpus":
        """
        `meta` needs `parent_asin` and either a `domain` column or the `domain` arg.

        Contract:
        - Item ids are ALWAYS namespaced "{domain}::{original id}" (there is no plain-id mode); the same asin in two
          domains gives two items. ``domain`` must be a non-empty string for every row.
        - Domain: the ``domain`` argument is a default for a missing ``domain`` column. If both are given they must
          agree (matching is fine and silent; any disagreement raises ValueError).
        - If `original_item_id` is present, `parent_asin` must already be namespaced (output of tag_domain):
          ``parent_asin == "{domain}::{original_item_id}"`` (or both equal an already-namespaced id of that domain);
          inconsistent rows raise ValueError. Otherwise `parent_asin` is the original id and is namespaced here.
        - ``categories``: missing -> none; string -> one category; list of strings -> many (blank/None skipped,
          de-duplicated). Malformed values raise ValueError (see normalize_categories).
        - ``price``: "$1,299.99" style strings are parsed; ranges / junk -> NULL. ``average_rating`` and
          ``rating_number``: non-numeric -> NULL with a warning; never rounded or truncated (rating_number is stored
          as given: INTEGER if every value is integral and none missing, otherwise REAL; SQLite compares both numerically).
        Extra columns are ignored; missing optional columns become NULL.
        """
        if "parent_asin" not in meta.columns:
            raise ValueError("metadata must have a 'parent_asin' column")
        df = meta.copy()
        if "domain" in df.columns:
            if domain is not None and not (df["domain"] == domain).all():
                found = sorted({str(d) for d in df.loc[df["domain"] != domain, "domain"]})[:3]
                raise ValueError(
                    f"domain={domain!r} conflicts with the 'domain' column (found {found}); "
                    "pass only one of them, or make them agree"
                )
        else:
            if domain is None:
                raise ValueError("pass domain=... or include a 'domain' column")
            df["domain"] = domain
        if not df["domain"].map(lambda d: isinstance(d, str) and bool(d.strip())).all():
            raise ValueError("every item needs a non-empty string domain (found missing or non-string domain values)")
        if not df["parent_asin"].map(lambda a: isinstance(a, str) and bool(a.strip())).all():
            raise ValueError("every item needs a non-empty string parent_asin (found missing or non-string values)")

        if "original_item_id" in df.columns:
            df["item_id"] = df["parent_asin"]
            original = df["original_item_id"]
            from_pipeline = df["item_id"] == pd.Series(
                [namespaced_item_id(d, o) for d, o in zip(df["domain"], original)], index=df.index
            )
            already_namespaced = (df["item_id"] == original) & pd.Series(
                [i.startswith(f"{d}{ITEM_ID_SEPARATOR}") for i, d in zip(df["item_id"], df["domain"])], index=df.index
            )
            inconsistent = ~(from_pipeline | already_namespaced)
            if inconsistent.any():
                examples = df.loc[inconsistent, ["parent_asin", "domain", "original_item_id"]].head(3).to_dict("records")
                raise ValueError(
                    "original_item_id is inconsistent with parent_asin/domain (expected parent_asin == "
                    f"'<domain>{ITEM_ID_SEPARATOR}<original_item_id>'); e.g. {examples}"
                )
        else:
            df["original_item_id"] = df["parent_asin"]
            df["item_id"] = [namespaced_item_id(d, a) for d, a in zip(df["domain"], df["parent_asin"])]

        if df["item_id"].duplicated().any():
            raise ValueError("duplicate item_id in metadata; de-duplicate before building the corpus")

        for col in ITEM_COLUMNS:
            if col not in df.columns:
                df[col] = None
        df["first_seen_ts"] = pd.to_numeric(df["first_seen_ts"], errors="coerce")
        df["price"] = pd.to_numeric(
            df["price"].astype("string").str.replace(r"[$,]", "", regex=True), errors="coerce"
        )  # "19.99" -> 19.99 ; null / ranges -> NaN -> NULL
        df["average_rating"] = numeric_column(df["average_rating"], "average_rating")
        df["rating_number"] = numeric_column(df["rating_number"], "rating_number")

        conn = sqlite3.connect(":memory:")
        conn.execute(ITEMS_TABLE_SCHEMA)
        df[list(ITEM_COLUMNS)].to_sql("items", conn, if_exists="append", index=False)

        cats = df["categories"] if "categories" in df.columns else pd.Series([None] * len(df))
        rows = []
        for item_id, cs in zip(df["item_id"], cats):
            for cat in normalize_categories(cs, item_id):
                rows.append((item_id, cat))
        conn.execute(CATEGORIES_TABLE_SCHEMA)
        conn.executemany("INSERT INTO item_categories VALUES (?, ?)", rows)

        for idx_sql in ITEMS_INDEXES:
            conn.execute(idx_sql)
        for idx_sql in CATEGORIES_INDEXES:
            conn.execute(idx_sql)

        # FTS5 over title/store/main_category plus joined categories (porter stems "keyboards" -> "keyboard").
        # External-content FTS cannot include categories (they live on item_categories), so we copy rowids.
        conn.execute(FTS_TABLE_SCHEMA)
        conn.execute(FTS_POPULATE_SQL)

        conn.commit()
        return cls(conn)

    @classmethod
    def from_parquet(cls, path: str | Path, domain: str | None = None) -> "ItemCorpus":
        return cls.from_dataframe(pd.read_parquet(path), domain=domain)

    # ---- reads ----------------------------------------------------------- #

    def select(
        self, sql: str, params: Sequence[Any] = (), max_rows: int = MAX_QUERY_ROWS
    ) -> tuple[list[dict[str, Any]], bool]:
        """Run one read-only SELECT. Returns (rows, truncated).

        The ``select``/``with`` prefix check below is only a friendly early error, NOT a security boundary or a
        SQL parser. The real protections are the read-only connection (``query_only`` + the authoriser that
        denies every non-read action, one-statement-only execution) and the time budget (progress handler).
        """
        sql = sql.strip().rstrip(";").strip()
        if not sql.lower().startswith(("select", "with")):
            raise ToolInputError("only SELECT statements are allowed")

        deadline = time.monotonic() + SQL_TIME_BUDGET_SECONDS
        self._conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
        try:
            # Add newline before closing paren to handle trailing -- comments
            wrapped_sql = f"SELECT * FROM (\n{sql}\n) LIMIT ?"
            cur = self._conn.execute(wrapped_sql, (*params, max_rows + 1))
            columns = [d[0] for d in cur.description]
            fetched = cur.fetchall()
        except (sqlite3.Error, sqlite3.Warning) as exc:
            if time.monotonic() > deadline:
                raise SQLTimeOutError(
                    "query exceeded the time budget. "
                    "Try narrowing with fewer domains/categories, or add keywords (for SemanticSearchTool), "
                    "or reduce the result limit."
                ) from exc
            raise ToolInputError(f"SQL error: {exc}. Schema: {SCHEMA_HINT}") from exc
        finally:
            self._conn.set_progress_handler(None, 0)

        truncated = len(fetched) > max_rows
        rows = [_clean_row(dict(zip(columns, r))) for r in fetched[:max_rows]]
        return rows, truncated

    def count(self, where_sql: str, params: Sequence[Any]) -> int:
        deadline = time.monotonic() + SQL_TIME_BUDGET_SECONDS
        self._conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
        try:
            cur = self._conn.execute(f"SELECT COUNT(*) FROM items WHERE {where_sql}", tuple(params))
            result = int(cur.fetchone()[0])
        except (sqlite3.Error, sqlite3.Warning) as exc:
            if time.monotonic() > deadline:
                raise SQLTimeOutError(
                    "query exceeded the time budget. "
                    "Try narrowing with fewer domains/categories, or add keywords (for SemanticSearchTool), "
                    "or reduce the result limit."
                ) from exc
            raise ToolInputError(f"SQL error: {exc}. Schema: {SCHEMA_HINT}") from exc
        finally:
            self._conn.set_progress_handler(None, 0)
        return result

    def domains(self) -> list[str]:
        return [r[0] for r in self._conn.execute("SELECT DISTINCT domain FROM items ORDER BY domain")]

    def item_domains(self, item_ids: Sequence[str]) -> dict[str, str]:
        """item_id -> domain, via the stored column (never by parsing the id)."""
        out: dict[str, str] = {}
        ids = list(item_ids)
        for i in range(0, len(ids), QUERY_CHUNK_SIZE):
            chunk = ids[i : i + QUERY_CHUNK_SIZE]
            marks = ",".join("?" * len(chunk))
            cur = self._conn.execute(f"SELECT item_id, domain FROM items WHERE item_id IN ({marks})", chunk)
            out.update(cur.fetchall())
        return out

    def categories(self) -> list[str]:
        """Return all distinct category names, sorted alphabetically."""
        return [r[0] for r in self._conn.execute("SELECT DISTINCT category FROM item_categories ORDER BY category")]

    def category_exists(self, category: str, case_sensitive: bool = True) -> bool:
        """
        Check if a category exists in the catalog.

        Args:
            category: Category name to check
            case_sensitive: If False, matches regardless of case (SQLite LOWER semantics for ASCII)

        Returns:
            True if category exists (exact match, or case-insensitive match if case_sensitive=False)
        """
        if case_sensitive:
            cur = self._conn.execute("SELECT 1 FROM item_categories WHERE category = ? LIMIT 1", (category,))
        else:
            # Case-insensitive for ASCII letters only (SQLite LOWER semantics)
            cur = self._conn.execute("SELECT 1 FROM item_categories WHERE LOWER(category) = LOWER(?) LIMIT 1", (category,))
        return cur.fetchone() is not None

    def normalize_category_case(self, category: str) -> str | None:
        """
        If category exists with different case only, return the canonical form.
        Otherwise return None.

        Args:
            category: Category name to normalize

        Returns:
            Canonical category name if exists with different case, None otherwise
        """
        if self.category_exists(category, case_sensitive=True):
            return category  # Already exact match
        if self.category_exists(category, case_sensitive=False):
            # Find the actual canonical form
            cur = self._conn.execute("SELECT DISTINCT category FROM item_categories WHERE LOWER(category) = LOWER(?)", (category,))
            row = cur.fetchone()
            return row[0] if row else None
        return None

    def suggest_categories(self, category: str, max_suggestions: int = 5) -> list[str]:
        """
        Suggest similar category names using string similarity.

        Args:
            category: Category name to find suggestions for
            max_suggestions: Maximum number of suggestions to return

        Returns:
            List of similar category names (at most max_suggestions)
        """
        all_cats = self.categories()
        if not all_cats:
            return []
        # Use difflib for fuzzy matching (built-in, no extra dependency)
        suggestions = difflib.get_close_matches(category, all_cats, n=max_suggestions, cutoff=0.6)
        return suggestions
