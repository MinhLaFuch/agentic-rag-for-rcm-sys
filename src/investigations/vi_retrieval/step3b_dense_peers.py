"""Step 3b: dense rank of each target among its category peers (restricted universe).

For each of the 196 targets:
  - encode the raw Vietnamese request text with e5base and bge-m3 (query prefixes)
  - score against restricted-universe doc vectors
  - restrict to universe peers sharing >=1 target category
  - rank of target within peers (1-based); NaN if target absent from universe

This approximates "category-constrained dense retrieval" — the universe holds
probe items + targets + random + same-category neighbors, so peer coverage is
partial (state caveat). GPU, seconds per model.

Outputs: step3_dense_peers.parquet
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import sqlite3
import torch

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

REQ = (ROOT / "experiments/agent_eval/campaigns/campaign_005/"
       "exp_5_agents_planner_inference_mode_template_reflect_rounds_0_multi_turn_True/run_1/requests.jsonl")
DB = ROOT / "resource/corpus/multi_domain/corpus_multi_domain.sqlite"


def main() -> None:
    eq11 = json.loads((ROOT / "investigations/eq11_target_predictability.json").read_text(encoding="utf-8"))
    per_target = eq11["per_target"]
    reqs = {}
    with open(REQ, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            reqs[r["request_id"]] = r["text"]

    # target -> categories (from eq11)
    tgt_cats = {t["target"]: set(t["target_cats"]) for t in per_target}

    # universe items + categories (parquet already carries the categories list)
    uitems = pd.read_parquet(OUT / "universe_items.parquet")
    uid_set = set(uitems["item_id"])
    item_cats: dict[str, set[str]] = {}
    for iid, cats in zip(uitems["item_id"], uitems["categories"]):
        if isinstance(cats, np.ndarray):
            cats = cats.tolist()
        if isinstance(cats, (list, tuple)):
            item_cats[iid] = {str(c) for c in cats if c}
        elif isinstance(cats, str) and cats:
            item_cats[iid] = {cats}

    # peers per target within universe — inverted index cat -> items
    from collections import defaultdict
    cat2items: dict[str, set[str]] = defaultdict(set)
    for iid, cs in item_cats.items():
        for c in cs:
            cat2items[c].add(iid)
    peer_of: dict[str, set[str]] = {}
    for t in per_target:
        tgt = t["target"]
        peers: set[str] = set()
        for c in tgt_cats[tgt]:
            peers |= cat2items.get(c, set())
        peers.discard(tgt)
        peer_of[tgt] = peers

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    from sentence_transformers import SentenceTransformer
    rows = []
    for model, qprefix in (("e5base", "query: "), ("bge-m3", "")):
        mdir = OUT / f"emb_{model}"
        dv = np.load(mdir / "doc_vectors.npy")
        universe_ids = json.loads((mdir / "item_ids.json").read_text())
        doc_pos = {iid: i for i, iid in enumerate(universe_ids)}
        D = torch.from_numpy(dv).to(dev).float()
        D = torch.nn.functional.normalize(D, dim=1)
        texts = [qprefix + reqs.get(t["request_id"], "") for t in per_target]
        model_st = SentenceTransformer(
            {"e5base": "intfloat/multilingual-e5-base", "bge-m3": "BAAI/bge-m3"}[model],
            device=dev)
        if model != "minilm":
            model_st = model_st.half()
        Q = model_st.encode(texts, batch_size=32, convert_to_numpy=True,
                            normalize_embeddings=True)
        Q = torch.from_numpy(np.asarray(Q, dtype=np.float32)).to(dev)
        Q = torch.nn.functional.normalize(Q, dim=1)
        S = Q @ D.T  # (196, 433555) ~ 340MB fp32 — ok
        S = S.cpu().numpy()
        for i, t in enumerate(per_target):
            tgt = t["target"]
            tp = doc_pos.get(tgt)
            peers = peer_of[tgt]
            if tp is None or not peers:
                rows.append({"model": model, "target": tgt, "request_id": t["request_id"],
                             "kind": t["kind"], "peer_rank": np.nan, "n_peers": len(peers)})
                continue
            peer_positions = np.array([doc_pos[p] for p in peers if p in doc_pos], dtype=np.int64)
            peer_scores = S[i, peer_positions]
            tscore = S[i, tp]
            # peers strictly better; tie-break by item_id asc like bm25 path
            better = int((peer_scores > tscore + 1e-9).sum())
            ties = [p for p, sc in zip(peer_positions, peer_scores)
                    if abs(sc - tscore) <= 1e-9 and universe_ids[int(p)] < tgt]
            rows.append({"model": model, "target": tgt, "request_id": t["request_id"],
                         "kind": t["kind"], "peer_rank": float(better + len(ties) + 1),
                         "n_peers": len(peers)})
        del D, S, Q, model_st
        if dev == "cuda":
            torch.cuda.empty_cache()

    df = pd.DataFrame(rows)
    df.to_parquet(OUT / "step3_dense_peers.parquet", index=False)
    for model, g in df.groupby("model"):
        r = g["peer_rank"]
        print(model, "n=", r.notna().sum(),
              "recall@10=", float((r <= 10).mean()),
              "recall@50=", float((r <= 50).mean()),
              "recall@200=", float((r <= 200).mean()),
              "median=", float(r.median()))


if __name__ == "__main__":
    main()
