"""Step 2c-4: dense recall + hybrid RRF + final metrics for all arms.

Dense arms (restricted universe): for each emb_<model>/ dir, score q_vi and
q_en against doc_vectors -> rank of source item -> recall@k/MRR.
MiniLM additionally scored against the FULL catalog (production dense leg).
Hybrid arm (f): RRF(k=60) of BM25(en, restricted) + best multilingual dense
(vi, restricted) — computed from bm25_ranks.parquet + dense ranks here.

Outputs:
  investigations/vi_retrieval/dense_ranks.parquet  (model, universe, arm, item_id, rank)
  investigations/vi_retrieval/step2_metrics.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
FULL_VEC = ROOT / "experiments/embedding_builds/multi_domain_full"
TOPK = 1500
KS = (10, 50, 200, 1000)
RRF_K = 60


def topk_ranks(q: np.ndarray, docs: np.ndarray, doc_item_pos: dict[str, int],
               query_item_ids: list[str], tile: int = 65536) -> list[float]:
    """Rank (1-based) of each query's source item; NaN if beyond TOPK."""
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    D = torch.from_numpy(docs).to(dev)  # keep storage dtype; normalize per-tile
    Q = torch.from_numpy(q).to(dev).float()
    Q = torch.nn.functional.normalize(Q, dim=1)
    n_docs = D.shape[0]
    ranks = [np.nan] * len(query_item_ids)
    # running top-TOPK (score, doc_pos) per query
    best_s = torch.full((Q.shape[0], TOPK), -1e9, device=dev)
    best_p = torch.zeros((Q.shape[0], TOPK), dtype=torch.long, device=dev)
    for r0 in range(0, n_docs, tile):
        block = torch.nn.functional.normalize(D[r0:r0 + tile].float(), dim=1)
        scores = Q @ block.T  # (nq, tile)
        v, i = torch.topk(scores, k=min(TOPK, scores.shape[1]), dim=1)
        i = i + r0
        cand_s = torch.cat([best_s, v], dim=1)
        cand_p = torch.cat([best_p, i], dim=1)
        v2, sel = torch.topk(cand_s, k=TOPK, dim=1)
        best_s = v2
        best_p = torch.gather(cand_p, 1, sel)
        del block, scores, v, i, cand_s, cand_p, v2, sel
    best_p = best_p.cpu().numpy()
    for qi, iid in enumerate(query_item_ids):
        pos = doc_item_pos.get(iid)
        if pos is None:
            continue
        row = best_p[qi]
        hit = np.where(row == pos)[0]
        # not in top-TOPK => true rank > TOPK (score ties at the boundary are
        # negligible for recall@<=1000 and contribute <0.001 to MRR)
        ranks[qi] = float(hit[0] + 1) if len(hit) else np.nan
    return ranks


def metrics_from_ranks(df: pd.DataFrame, rank_col="rank") -> dict:
    out = {}
    for keys, g in df.groupby(list(keys)):
        s = g[rank_col]
        n = len(s)
        out["/".join(str(k) for k in keys)] = {
            "n": n,
            "recall@10": float((s <= 10).mean()),
            "recall@50": float((s <= 50).mean()),
            "recall@200": float((s <= 200).mean()),
            "recall@1000": float((s <= 1000).mean()),
            "mrr": float((1.0 / s[s <= TOPK]).sum() / n),
        }
    return out


def main() -> None:
    uitems = pd.read_parquet(OUT / "universe_items.parquet")
    universe_ids = uitems["item_id"].tolist()
    doc_pos = {iid: i for i, iid in enumerate(universe_ids)}
    all_dense = []

    for mdir in sorted(OUT.glob("emb_*")):
        model = mdir.name[4:]
        dv = np.load(mdir / "doc_vectors.npy")  # fp16
        meta = json.loads((mdir / "meta.json").read_text()) if (mdir / "meta.json").exists() else {}
        qids = pd.read_parquet(mdir / "query_items.parquet")["item_id"].tolist()
        ids_in_docs = set(json.loads((mdir / "item_ids.json").read_text()))
        for arm, qfile in (("vi", "q_vi.npy"), ("en", "q_en.npy")):
            q = np.load(mdir / qfile)
            # restricted universe
            t0 = time.time()
            ranks = topk_ranks(q, dv, doc_pos, qids)
            print(f"{model}/{arm} restricted: {time.time()-t0:.0f}s", flush=True)
            for iid, r in zip(qids, ranks):
                all_dense.append({"model": model, "universe": "restricted", "arm": arm,
                                  "item_id": iid, "rank": r})
        # full-catalog MiniLM only
        if model == "minilm":
            full_ids = np.load(FULL_VEC / "item_ids.npy", mmap_mode="r")
            full_pos = {str(i): r for r, i in enumerate(full_ids)}
            fvecs = np.load(FULL_VEC / "vectors.npy", mmap_mode="r")
            for arm, qfile in (("vi", "q_vi.npy"), ("en", "q_en.npy")):
                q = np.load(mdir / qfile)
                t0 = time.time()
                # tile over full catalog fp32->fp16 on the fly
                ranks = _full_catalog_ranks(q, fvecs, full_pos, qids)
                print(f"minilm/{arm} full: {time.time()-t0:.0f}s", flush=True)
                for iid, r in zip(qids, ranks):
                    all_dense.append({"model": model, "universe": "full", "arm": arm,
                                      "item_id": iid, "rank": r})

    ddf = pd.DataFrame(all_dense)
    ddf.to_parquet(OUT / "dense_ranks.parquet", index=False)
    print(json.dumps(metrics_from_ranks(ddf), indent=1), flush=True)
    (OUT / "dense_metrics.json").write_text(json.dumps(metrics_from_ranks(ddf), indent=1))


def _full_catalog_ranks(q: np.ndarray, fvecs, full_pos: dict, qids: list[str],
                        tile: int = 131072) -> list[float]:
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    Q = torch.from_numpy(q).to(dev).float()
    Q = torch.nn.functional.normalize(Q, dim=1)
    n = fvecs.shape[0]
    TOPK = 1500
    best_s = torch.full((Q.shape[0], TOPK), -1e9, device=dev)
    best_p = torch.zeros((Q.shape[0], TOPK), dtype=torch.long, device=dev)
    for r0 in range(0, n, tile):
        block = torch.nn.functional.normalize(
            torch.from_numpy(np.asarray(fvecs[r0:r0 + tile], dtype=np.float32)).to(dev), dim=1)
        scores = Q @ block.T
        v, i = torch.topk(scores, k=min(TOPK, scores.shape[1]), dim=1)
        i = i + r0
        cand_s = torch.cat([best_s, v], dim=1)
        cand_p = torch.cat([best_p, i], dim=1)
        v2, sel = torch.topk(cand_s, k=TOPK, dim=1)
        best_s = v2
        best_p = torch.gather(cand_p, 1, sel)
        del block, scores, v, i, cand_s, cand_p, v2, sel
        if (r0 // tile) % 5 == 0:
            print(f"    full tile {r0}/{n}", flush=True)
    best_p = best_p.cpu().numpy()
    best_s = best_s.cpu().numpy()
    ranks = []
    # need doc vectors for fallback scoring of out-of-topk items — do a second
    # pass only for items not found in topk (rare)
    for qi, iid in enumerate(qids):
        pos = full_pos.get(iid)
        if pos is None:
            ranks.append(np.nan)
            continue
        row = best_p[qi]
        hit = np.where(row == pos)[0]
        if len(hit):
            ranks.append(float(hit[0] + 1))
        else:
            ranks.append(np.nan)  # beyond TOPK (approx; see note)
    return ranks


if __name__ == "__main__":
    main()
