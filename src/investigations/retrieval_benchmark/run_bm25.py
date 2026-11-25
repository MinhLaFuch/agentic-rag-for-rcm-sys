"""BM25 (production FTS5 path) ranks on the FULL catalog for benchmark queries.

Arms:
  desc_vi / desc_en   — LLM descriptive VI query per target (+ its EN translation)
  req_vi / req_en     — original campaign request text per request (+ faithful EN)

Replicates SearchTool's lexical leg: _tokenize -> OR-match ->
ORDER BY -bm25(items_fts) DESC, rating_number DESC, item_id. Fetches top-1500;
rank >1500 recorded as NaN.

Output: bm25_ranks.parquet  columns: arm, item_id, rank
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
VI_DIR = ROOT / "investigations/vi_retrieval"
sys.path.insert(0, str(ROOT))

from package.tools.retrieval._helper import _tokenize  # noqa: E402

DB = ROOT / "resource/corpus/multi_domain/corpus_multi_domain.sqlite"
TOP_FETCH = 1500


def load_query_map() -> dict[str, dict[str, str]]:
    """item_id -> {desc_vi, desc_en}; request_id -> {req_vi, req_en}."""
    qmap: dict[str, dict[str, str]] = {}
    vi_path = OUT / "target_queries.jsonl"
    en_path = OUT / "target_query_translations.jsonl"
    en = {}
    if en_path.exists():
        for l in en_path.read_text(encoding="utf-8").splitlines():
            if l.strip():
                d = json.loads(l)
                en[d["item_id"]] = d.get("en_query") or d.get("en") or ""
    for l in vi_path.read_text(encoding="utf-8").splitlines():
        if l.strip():
            d = json.loads(l)
            qmap[d["item_id"]] = {"desc_vi": d["vi_query"], "desc_en": en.get(d["item_id"], "")}

    req_en = {}
    for l in (VI_DIR / "request_translations.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            d = json.loads(l)
            req_en[d["request_id"]] = d.get("en") or d.get("en_text") or ""
    return qmap, req_en


def bm25_rank(conn: sqlite3.Connection, query: str, target_id: str) -> float:
    tokens = _tokenize(query)
    if not tokens:
        return np.nan
    match = " OR ".join(f'"{t}"' for t in tokens)
    sql = (
        "SELECT items.item_id FROM items_fts JOIN items ON items.rowid = items_fts.rowid "
        "WHERE items_fts MATCH ? ORDER BY -bm25(items_fts) DESC, items.rating_number DESC, items.item_id "
        f"LIMIT {TOP_FETCH}"
    )
    for i, (iid,) in enumerate(conn.execute(sql, (match,)), start=1):
        if iid == target_id:
            return float(i)
    return np.nan


def main() -> None:
    df = pd.read_parquet(OUT / "targets.parquet")
    qmap, req_en = load_query_map()

    jobs = []  # (arm, query_text, target_item_id)
    for r in df.itertuples(index=False):
        q = qmap.get(r.item_id, {})
        if q.get("desc_vi"):
            jobs.append(("desc_vi", q["desc_vi"], r.item_id))
            if q.get("desc_en"):
                jobs.append(("desc_en", q["desc_en"], r.item_id))
        jobs.append(("req_vi", r.request_text, r.item_id))
        en = req_en.get(r.request_id, "")
        if en:
            jobs.append(("req_en", en, r.item_id))
    print(f"bm25 jobs: {len(jobs)}", flush=True)

    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.execute("PRAGMA cache_size=-2000000")
    rows = []
    t0 = time.time()
    for i, (arm, query, target) in enumerate(jobs):
        rows.append({"arm": arm, "item_id": target, "rank": bm25_rank(conn, query, target)})
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(jobs)} ({time.time()-t0:.0f}s)", flush=True)
    out = pd.DataFrame(rows)
    out.to_parquet(OUT / "bm25_ranks.parquet", index=False)
    print(f"wrote bm25_ranks.parquet in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    sys.exit(main())
