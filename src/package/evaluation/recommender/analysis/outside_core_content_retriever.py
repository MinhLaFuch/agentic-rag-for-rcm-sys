"""History-only lexical probe over visible items excluded from the CF core."""
import sqlite3
import time

from .history_title_query import history_title_query
from ....tools.retrieval.tokenize_search_query import tokenize_search_query


class OutsideCoreContentRetriever:
    def __init__(self, connection, core_ids, cutoff, *, timeout_seconds=5):
        if cutoff <= 0 or timeout_seconds <= 0:
            raise ValueError("positive cutoff and timeout required")
        self.conn, self.cutoff, self.timeout = connection, cutoff, timeout_seconds
        # Only TEMP objects are written; the source connection is opened mode=ro.
        self.conn.execute("CREATE TEMP TABLE probe_core(item_id TEXT PRIMARY KEY)")
        self.conn.executemany("INSERT INTO probe_core VALUES (?)", ((i,) for i in core_ids))
        self.conn.execute("CREATE VIRTUAL TABLE temp.probe_fts USING fts5(item_id UNINDEXED, title, store, main_category, tokenize='porter unicode61')")
        self.conn.execute("""INSERT INTO probe_fts(rowid,item_id,title,store,main_category)
            SELECT i.rowid,i.item_id,i.title,i.store,i.main_category FROM main.items i
            WHERE i.first_seen_ts IS NOT NULL AND i.first_seen_ts <= ?
            AND NOT EXISTS (SELECT 1 FROM probe_core c WHERE c.item_id=i.item_id)""", (cutoff,))
        self.visible_items = self.conn.execute("SELECT COUNT(*) FROM probe_fts").fetchone()[0]

    def retrieve(self, history_ids, *, limit=100, excluded_ids=None):
        if limit < 1:
            raise ValueError("positive candidate limit required")
        titles = []
        # This API accepts history IDs only, never targets or target metadata.
        for item in history_ids:
            row = self.conn.execute("SELECT title FROM main.items WHERE item_id=? AND first_seen_ts<=?", (item, self.cutoff)).fetchone()
            if row:
                titles.append(row[0] or "")
        query = history_title_query(titles)
        tokens = tokenize_search_query(query)
        if not tokens:
            return {"status": "no_query", "query": query, "candidates": [], "error": None}
        match = " OR ".join('"' + token + '"' for token in tokens)
        started = time.perf_counter()
        seen = set(history_ids) | set(excluded_ids or [])
        self.conn.set_progress_handler(lambda: int(time.perf_counter() - started >= self.timeout), 10000)
        try:
            # Overfetch enough to remove seen IDs without reducing the budget.
            # FTS5's hidden rank column can stream Top-K directly. Sorting by
            # bm25() plus an extra key forces a full temporary sort instead.
            rows = self.conn.execute("""SELECT item_id, -rank AS score FROM probe_fts
                WHERE probe_fts MATCH ? ORDER BY rank LIMIT ?""",
                (match, limit + len(seen))).fetchall()
            rows.sort(key=lambda row:(-row[1],row[0]))
            ids = [r[0] for r in rows if r[0] not in seen][:limit]
            return {"status": "ok", "query": query, "candidates": ids, "error": None}
        except sqlite3.OperationalError as exc:
            return {"status": "error", "query": query, "candidates": [], "error": str(exc)}
        finally:
            self.conn.set_progress_handler(None, 0)
