"""
Read-only item store shared by QueryTool and SQLTool (and used by ItemCFTool /
RecoModelTool to attach domain).

Built once from a metadata DataFrame, then locked: `query_only` pragma plus an
authoriser that only allows SELECT.  Item ids are namespaced
"{domain}::{parent_asin}"; the domain is stored as a column and looked up, never
parsed from the id (D-010).
"""

from __future__ import annotations

import sqlite3
import time
import warnings
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from ...data import namespaced_item_id
from ..base import ToolInputError
from .._limits import MAX_QUERY_ROWS, SQL_TIME_BUDGET_SECONDS
from .._schema import ITEM_COLUMNS, SCHEMA_HINT
from ._helper import _clean_row, read_only_authorizer



class ItemCorpus:
    """
    Read-only item store.  Built once from a metadata DataFrame, then locked:
    query_only pragma + an authoriser that only allows SELECT, so neither tool
    can modify or exfiltrate anything beyond reading the two tables.
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
        If `original_item_id` is present, `parent_asin` is assumed already namespaced
        (output of domain_registry.tag_domain); otherwise it is namespaced here.
        Extra columns are ignored; missing optional columns become NULL.
        """
        if "parent_asin" not in meta.columns:
            raise ValueError("metadata must have a 'parent_asin' column")
        df = meta.copy()
        if "domain" not in df.columns:
            if domain is None:
                raise ValueError("pass domain=... or include a 'domain' column")
            df["domain"] = domain
        elif domain is not None:
            # Warn if both domain= arg and domain column are present
            warnings.warn(
                f"Both domain= argument ('{domain}') and 'domain' column are present. "
                "Using the column value; the argument is ignored.",
                UserWarning,
                stacklevel=2
            )

        if "original_item_id" in df.columns:
            df["item_id"] = df["parent_asin"]
            # Warn if item_id doesn't contain '::' when original_item_id is present
            # (suggests the data wasn't properly namespaced)
            if not df["item_id"].str.contains("::", na=False).all():
                warnings.warn(
                    "original_item_id is present but some item_id values don't contain '::'. "
                    "This suggests the data wasn't properly namespaced. "
                    "Ensure parent_asin is already namespaced when using original_item_id.",
                    UserWarning,
                    stacklevel=2
                )
        else:
            df["original_item_id"] = df["parent_asin"]
            df["item_id"] = [namespaced_item_id(d, a) for d, a in zip(df["domain"], df["parent_asin"])]

        if df["item_id"].duplicated().any():
            raise ValueError("duplicate item_id in metadata; de-duplicate before building the corpus")

        for col in ITEM_COLUMNS:
            if col not in df.columns:
                df[col] = None
        df["price"] = pd.to_numeric(
            df["price"].astype("string").str.replace(r"[$,]", "", regex=True), errors="coerce"
        )  # "19.99" -> 19.99 ; null / ranges -> NaN -> NULL
        df["rating_number"] = pd.to_numeric(df["rating_number"], errors="coerce")

        conn = sqlite3.connect(":memory:")
        df[list(ITEM_COLUMNS)].to_sql("items", conn, index=False)

        cats = df["categories"] if "categories" in df.columns else pd.Series([None] * len(df))
        rows = [
            (item_id, str(cat))
            for item_id, cs in zip(df["item_id"], cats)
            if cs is not None and not (isinstance(cs, float) and np.isnan(cs))
            for cat in list(cs)
        ]
        conn.execute("CREATE TABLE item_categories (item_id TEXT, category TEXT)")
        conn.executemany("INSERT INTO item_categories VALUES (?, ?)", rows)

        conn.execute("CREATE UNIQUE INDEX idx_items_id ON items(item_id)")
        conn.execute("CREATE INDEX idx_items_domain ON items(domain)")
        conn.execute("CREATE INDEX idx_items_price ON items(price)")
        conn.execute("CREATE INDEX idx_cat_item ON item_categories(item_id)")
        conn.execute("CREATE INDEX idx_cat_cat ON item_categories(category)")

        # FTS5 over title/store/main_category plus joined categories (porter stems "keyboards" -> "keyboard").
        # External-content FTS cannot include categories (they live on item_categories), so we copy rowids.
        conn.execute(
            "CREATE VIRTUAL TABLE items_fts USING fts5("
            "title, store, main_category, categories, tokenize='porter unicode61')"
        )
        conn.execute(
            "INSERT INTO items_fts(rowid, title, store, main_category, categories) "
            "SELECT i.rowid, i.title, i.store, i.main_category, "
            "COALESCE((SELECT group_concat(c.category, ' ') FROM item_categories c "
            "WHERE c.item_id = i.item_id), '') "
            "FROM items i"
        )

        conn.commit()
        return cls(conn)

    @classmethod
    def from_parquet(cls, path: str | Path, domain: str | None = None) -> "ItemCorpus":
        return cls.from_dataframe(pd.read_parquet(path), domain=domain)

    # ---- reads ----------------------------------------------------------- #

    def select(
        self, sql: str, params: Sequence[Any] = (), max_rows: int = MAX_QUERY_ROWS
    ) -> tuple[list[dict[str, Any]], bool]:
        """Run one read-only SELECT. Returns (rows, truncated)."""
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
        for i in range(0, len(ids), 500):
            chunk = ids[i : i + 500]
            marks = ",".join("?" * len(chunk))
            cur = self._conn.execute(f"SELECT item_id, domain FROM items WHERE item_id IN ({marks})", chunk)
            out.update(cur.fetchall())
        return out
