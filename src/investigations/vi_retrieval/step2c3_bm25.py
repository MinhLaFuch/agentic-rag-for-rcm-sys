"""Step 2c-3: BM25 recall — production FTS5 path, both universes.

Replicates SearchTool's lexical leg exactly: _tokenize() -> OR-match ->
ORDER BY -bm25(items_fts) DESC, rating_number DESC, item_id. For each probe
query (raw VI + LLM-English translation) find the rank of the SOURCE item.

Top-1500 fetch per query: ranks beyond that are recorded as >1500 (recall@1000
unaffected; MRR contribution of such ranks is <0.001 anyway).

Outputs: investigations/vi_retrieval/bm25_ranks.parquet
  columns: arm(vi|en), universe(restricted|full), item_id, rank (NaN => >1500)
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
sys.path.insert(0, str(ROOT))

from package.tools.retrieval._helper import _tokenize  # noqa: E402

DBS = {
    "restricted": OUT / "restricted_corpus.sqlite",
    "full": ROOT / "resource/corpus/multi_domain/corpus_multi_domain.sqlite",
}
TOP_FETCH = 1500


def queries() -> pd.DataFrame:
    vi = [json.loads(l) for l in (OUT / "vi_queries.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    tr = {}
    tr_path = OUT / "vi_query_translations.jsonl"
    if tr_path.exists():
        for l in tr_path.read_text(encoding="utf-8").splitlines():
            if l.strip():
                d = json.loads(l)
                tr[d["item_id"]] = d.get("en_query") or d.get("en")
    rows = []
    for q in vi:
        rows.append({"item_id": q["item_id"], "vi": q["vi_query"], "en": tr.get(q["item_id"], "")})
    return pd.DataFrame(rows)


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
    try:
        rows = conn.execute(sql, (match,)).fetchall()
    except sqlite3.Error:
        return np.nan
    for rank, (iid,) in enumerate(rows, 1):
        if iid == target_id:
            return float(rank)
    return np.nan


def run_db(name: str, db_path: Path, qdf: pd.DataFrame) -> list[dict]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    out = []
    t0 = time.time()
    n = len(qdf)
    for qi, row in enumerate(qdf.itertuples(index=False)):
        for arm, q in (("vi", row.vi), ("en", row.en)):
            if not q:
                continue
            r = bm25_rank(conn, q, row.item_id)
            out.append({"universe": name, "arm": arm, "item_id": row.item_id, "rank": r})
        if (qi + 1) % 50 == 0:
            print(f"  {name}: {qi+1}/{n} queries ({time.time()-t0:.0f}s)", flush=True)
    conn.close()
    return out


def main() -> None:
    qdf = queries()
    print(f"{len(qdf)} probe queries", flush=True)
    all_rows = []
    for name, path in DBS.items():
        if not path.exists():
            print(f"SKIP {name}: {path} missing", file=sys.stderr, flush=True)
            continue
        print(f"BM25 on {name} ({path.name}) ...", flush=True)
        all_rows.extend(run_db(name, path, qdf))
    df = pd.DataFrame(all_rows)
    df.to_parquet(OUT / "bm25_ranks.parquet", index=False)
    summ = df.groupby(["universe", "arm"])["rank"].apply(
        lambda s: pd.Series({
            "n": len(s),
            "found<=1000": int((s <= 1000).sum()),
            "found<=200": int((s <= 200).sum()),
            "found<=50": int((s <= 50).sum()),
            "found<=10": int((s <= 10).sum()),
            "mrr": float((1.0 / s[s <= TOP_FETCH]).sum() / len(s)),
        })).unstack()
    print(summ.to_string(), flush=True)
    (OUT / "bm25_ranks_summary.json").write_text(summ.to_json())


if __name__ == "__main__":
    main()
