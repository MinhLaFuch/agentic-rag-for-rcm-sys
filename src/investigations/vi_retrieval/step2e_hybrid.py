"""Step 2e: arm (f) hybrid = RRF(BM25(en translated), multilingual-dense(raw VI)).

Needs full top-k lists (only source-item ranks were stored before):
  - BM25 restricted top-1500 item ids per en query  (recomputed, ~minutes)
  - dense restricted top-1500 positions per vi query (GPU, seconds)

RRF(k=60) over the two lists -> fused rank of source item -> recall/MRR.
Computed for both multilingual models (bge-m3, e5base); best reported.

Outputs: investigations/vi_retrieval/hybrid_ranks.parquet + step2_metrics.json[f_*]
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DB = OUT / "restricted_corpus.sqlite"
TOPK = 1500
RRF_K = 60
KS = (10, 50, 200, 1000)
sys.path.insert(0, str(ROOT))
from package.tools.retrieval._helper import _tokenize  # noqa: E402


def bm25_topk(conn, query: str, k: int) -> list[str]:
    toks = _tokenize(query)
    if not toks:
        return []
    match = " OR ".join(f'"{t}"' for t in toks)
    sql = ("SELECT items.item_id FROM items_fts JOIN items ON items.rowid=items_fts.rowid "
           "WHERE items_fts MATCH ? ORDER BY -bm25(items_fts) DESC, items.rating_number DESC, items.item_id "
           f"LIMIT {k}")
    try:
        return [r[0] for r in conn.execute(sql, (match,)).fetchall()]
    except sqlite3.Error:
        return []


def dense_topk(q: np.ndarray, docs: np.ndarray, k: int = TOPK) -> np.ndarray:
    """Return (n_queries, k) doc positions by score desc, -1 padded."""
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    D = torch.from_numpy(docs).to(dev).float()
    D = torch.nn.functional.normalize(D, dim=1)
    Q = torch.from_numpy(q).to(dev).float()
    Q = torch.nn.functional.normalize(Q, dim=1)
    n = D.shape[0]
    best_s = torch.full((Q.shape[0], k), -1e9, device=dev)
    best_p = torch.zeros((Q.shape[0], k), dtype=torch.long, device=dev)
    tile = 65536
    for r0 in range(0, n, tile):
        block = D[r0:r0 + tile]
        scores = Q @ block.T
        v, i = torch.topk(scores, k=min(k, scores.shape[1]), dim=1)
        i = i + r0
        cs = torch.cat([best_s, v], 1)
        cp = torch.cat([best_p, i], 1)
        v2, sel = torch.topk(cs, k=k, dim=1)
        best_s, best_p = v2, torch.gather(cp, 1, sel)
    return best_p.cpu().numpy()


def rrf_fuse(list_a: list[str], list_b_pos: np.ndarray, pos2iid: list[str],
             k: int = RRF_K) -> dict[str, float]:
    """Fuse BM25 id-list (rank order) with dense position-list -> {item_id: rrf_score}."""
    scores: dict[str, float] = {}
    for rank, iid in enumerate(list_a, 1):
        scores[iid] = scores.get(iid, 0.0) + 1.0 / (k + rank)
    for rank, pos in enumerate(list_b_pos, 1):
        if pos < 0:
            break
        iid = pos2iid[int(pos)]
        scores[iid] = scores.get(iid, 0.0) + 1.0 / (k + rank)
    return scores


def rank_of(scores: dict[str, float], target: str) -> float:
    if target not in scores:
        return np.nan
    ts = scores[target]
    better = sum(1 for v in scores.values() if v > ts + 1e-12)
    # ties: deterministic by item_id like production
    ties = [iid for iid, v in scores.items() if abs(v - ts) <= 1e-12]
    better += sum(1 for iid in ties if iid < target)
    return float(better + 1)


def metrics(ranks: pd.Series) -> dict:
    s = ranks.dropna().astype(float)
    n = len(ranks)
    out = {"n": int(n)}
    for k in KS:
        out[f"recall@{k}"] = float((s <= k).sum() / n)
    out["mrr"] = float((1.0 / s[s <= TOPK]).sum() / n)
    return out


def main() -> None:
    vi = [json.loads(l) for l in (OUT / "vi_queries.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    tr = {}
    for l in (OUT / "vi_query_translations.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            d = json.loads(l)
            tr[d["item_id"]] = d.get("en_query") or d.get("en") or ""
    queries = pd.DataFrame([{"item_id": q["item_id"], "vi": q["vi_query"],
                             "en": tr.get(q["item_id"], "")} for q in vi])

    # BM25 restricted top-k lists for EN (translated) queries
    cache = OUT / "bm25_topk_restricted_en.parquet"
    if cache.exists():
        bm_lists = pd.read_parquet(cache)
    else:
        conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        rows = []
        t0 = time.time()
        for i, row in enumerate(queries.itertuples(index=False)):
            rows.append({"item_id": row.item_id, "topk": bm25_topk(conn, row.en, TOPK)})
            if (i + 1) % 50 == 0:
                print(f"bm25 {i+1}/510 ({time.time()-t0:.0f}s)", flush=True)
        conn.close()
        bm_lists = pd.DataFrame(rows)
        bm_lists.to_parquet(cache, index=False)

    # dense top-k positions for vi queries, per multilingual model
    uitems = pd.read_parquet(OUT / "universe_items.parquet")
    universe_ids = uitems["item_id"].tolist()
    all_rows = []
    for model in ("bge-m3", "e5base"):
        mdir = OUT / f"emb_{model}"
        dv = np.load(mdir / "doc_vectors.npy")  # fp16
        q = np.load(mdir / "q_vi.npy")
        t0 = time.time()
        pos = dense_topk(q, dv)
        print(f"{model} dense topk done ({time.time()-t0:.0f}s)", flush=True)
        bm_map = dict(zip(bm_lists["item_id"], bm_lists["topk"]))
        for i, row in enumerate(queries.itertuples(index=False)):
            scores = rrf_fuse(bm_map.get(row.item_id, []), pos[i], universe_ids)
            all_rows.append({"model": model, "item_id": row.item_id,
                             "rank": rank_of(scores, row.item_id)})

    df = pd.DataFrame(all_rows)
    df.to_parquet(OUT / "hybrid_ranks.parquet", index=False)
    for model, g in df.groupby("model"):
        print(model, json.dumps(metrics(g["rank"]), indent=1), flush=True)


if __name__ == "__main__":
    main()
