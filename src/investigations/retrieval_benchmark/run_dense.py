"""Dense retrieval ranks for the retrieval benchmark.

Models/universes:
  minilm   all-MiniLM-L6-v2  -> FULL catalog (existing embedding build, 2.64M x 384)
  e5base   multilingual-e5-base -> restricted universe (433k, incl. all 196 targets)
  bge-m3   BAAI/bge-m3       -> restricted universe

Arms per model: {desc,req}_{vi,en} — same query texts as run_bm25.py.
Restricted-universe numbers are INFLATED in absolute terms (smaller candidate
pool); valid for relative arm comparison only.

Output: dense_ranks.parquet  columns: model, universe, arm, item_id, rank
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
VI_DIR = ROOT / "investigations/vi_retrieval"
FULL_VEC = ROOT / "experiments/embedding_builds/multi_domain_full"
sys.path.insert(0, str(ROOT))

MODELS = {
    "minilm": {"hf": "sentence-transformers/all-MiniLM-L6-v2", "q_prefix": "", "universe": "full"},
    "e5base": {"hf": "intfloat/multilingual-e5-base", "q_prefix": "query: ", "universe": "restricted"},
    "bge-m3": {"hf": "BAAI/bge-m3", "q_prefix": "", "universe": "restricted"},
}
TOPK = 1500
TILE = 131072
Q_BATCH = 64


def load_jobs() -> pd.DataFrame:
    """One row per (arm, item_id, query_text) — mirrors run_bm25.py arms."""
    df = pd.read_parquet(OUT / "targets.parquet")
    en = {}
    en_path = OUT / "target_query_translations.jsonl"
    if en_path.exists():
        for l in en_path.read_text(encoding="utf-8").splitlines():
            if l.strip():
                d = json.loads(l)
                en[d["item_id"]] = d.get("en_query") or d.get("en") or ""
    vi = {}
    vi_path = OUT / "target_queries.jsonl"
    if vi_path.exists():
        for l in vi_path.read_text(encoding="utf-8").splitlines():
            if l.strip():
                d = json.loads(l)
                vi[d["item_id"]] = d["vi_query"]
    req_en = {}
    for l in (VI_DIR / "request_translations.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            d = json.loads(l)
            req_en[d["request_id"]] = d.get("en") or ""

    rows = []
    for r in df.itertuples(index=False):
        if r.item_id in vi:
            rows.append({"arm": "desc_vi", "item_id": r.item_id, "query": vi[r.item_id]})
            if en.get(r.item_id):
                rows.append({"arm": "desc_en", "item_id": r.item_id, "query": en[r.item_id]})
        rows.append({"arm": "req_vi", "item_id": r.item_id, "query": r.request_text})
        if req_en.get(r.request_id):
            rows.append({"arm": "req_en", "item_id": r.item_id, "query": req_en[r.request_id]})
    return pd.DataFrame(rows)


def encode_texts(model, texts: list[str]) -> np.ndarray:
    from sentence_transformers import SentenceTransformer
    st = SentenceTransformer(model["hf"])
    if torch.cuda.is_available():
        st = st.cuda()
    q = [model["q_prefix"] + t for t in texts]
    emb = st.encode(q, batch_size=Q_BATCH, convert_to_numpy=True, show_progress_bar=False)
    return emb.astype(np.float32)


def topk_positions(Q: np.ndarray, doc_iter, n_docs: int) -> np.ndarray:
    """Return (nq, TOPK) doc positions of top-scoring docs per query."""
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    Qt = torch.from_numpy(Q).to(dev)
    Qt = torch.nn.functional.normalize(Qt, dim=1)
    best_s = torch.full((Qt.shape[0], TOPK), -1e9, device=dev)
    best_p = torch.zeros((Qt.shape[0], TOPK), dtype=torch.long, device=dev)
    for r0, block_np in doc_iter:
        block = torch.nn.functional.normalize(
            torch.from_numpy(np.asarray(block_np, dtype=np.float32)).to(dev), dim=1)
        scores = Qt @ block.T
        v, i = torch.topk(scores, k=min(TOPK, scores.shape[1]), dim=1)
        i = i + r0
        cand_s = torch.cat([best_s, v], dim=1)
        cand_p = torch.cat([best_p, i], dim=1)
        v2, sel = torch.topk(cand_s, k=TOPK, dim=1)
        best_s, best_p = v2, torch.gather(cand_p, 1, sel)
        del block, scores, v, i, cand_s, cand_p, v2, sel
    return best_p.cpu().numpy()


def doc_iter_from_array(docs: np.ndarray, tile: int = TILE):
    for r0 in range(0, docs.shape[0], tile):
        yield r0, docs[r0:r0 + tile]


def doc_iter_from_memmap(vecs, tile: int = TILE):
    for r0 in range(0, vecs.shape[0], tile):
        yield r0, np.asarray(vecs[r0:r0 + tile])


def main() -> None:
    jobs = load_jobs()
    print(f"dense jobs: {len(jobs)}  arms: {jobs.arm.value_counts().to_dict()}", flush=True)

    results = []
    st_models: dict[str, object] = {}

    for model_name, cfg in MODELS.items():
        t0 = time.time()
        if cfg["universe"] == "full":
            vecs = np.load(FULL_VEC / "vectors.npy", mmap_mode="r")
            ids = np.load(FULL_VEC / "item_ids.npy", mmap_mode="r")
            doc_pos = {str(i): r for r, i in enumerate(ids)}
            n_docs, it = vecs.shape[0], doc_iter_from_memmap(vecs)
            it_factory = lambda: doc_iter_from_memmap(vecs)  # noqa: E731
        else:
            mdir = VI_DIR / f"emb_{model_name}"
            dv = np.load(mdir / "doc_vectors.npy")
            ids = json.loads((mdir / "item_ids.json").read_text())
            doc_pos = {iid: i for i, iid in enumerate(ids)}
            n_docs = dv.shape[0]
            it_factory = lambda dv=dv: doc_iter_from_array(dv)  # noqa: E731

        # encode all unique query texts once
        uniq = list(dict.fromkeys(jobs["query"].tolist()))
        if model_name not in st_models:
            st_models[model_name] = cfg  # marker; SentenceTransformer loaded per encode call is slow,
        # load model once via a small cache on the function
        Q = _encode_cached(model_name, cfg, uniq)
        best_p = topk_positions(Q, it_factory(), n_docs)
        pos_of = {t: i for i, t in enumerate(uniq)}

        for r in jobs.itertuples(index=False):
            qi = pos_of[r.query]
            pos = doc_pos.get(r.item_id)
            rank = np.nan
            if pos is not None:
                hit = np.where(best_p[qi] == pos)[0]
                if len(hit):
                    rank = float(hit[0] + 1)
            results.append({"model": model_name, "universe": cfg["universe"],
                            "arm": r.arm, "item_id": r.item_id, "rank": rank})
        print(f"{model_name}: {len(results)} rows cumulative, {time.time()-t0:.0f}s", flush=True)

    out = pd.DataFrame(results)
    out.to_parquet(OUT / "dense_ranks.parquet", index=False)
    print("wrote dense_ranks.parquet", flush=True)


_ST_CACHE: dict[str, object] = {}


def _encode_cached(model_name: str, cfg: dict, texts: list[str]) -> np.ndarray:
    if model_name not in _ST_CACHE:
        from sentence_transformers import SentenceTransformer
        st = SentenceTransformer(cfg["hf"])
        if torch.cuda.is_available():
            st = st.cuda()
        _ST_CACHE[model_name] = st
    st = _ST_CACHE[model_name]
    q = [cfg["q_prefix"] + t for t in texts]
    emb = st.encode(q, batch_size=Q_BATCH, convert_to_numpy=True, show_progress_bar=False)
    return emb.astype(np.float32)


if __name__ == "__main__":
    sys.exit(main())
