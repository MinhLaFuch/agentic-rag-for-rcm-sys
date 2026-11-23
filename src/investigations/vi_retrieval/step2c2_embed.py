"""Step 2c-2: embed the restricted universe + probe queries with each model.

Models:
  minilm   — reuse full-catalog vectors (experiments/embedding_builds/
             multi_domain_full); gather universe rows only. Queries encoded
             fresh with all-MiniLM-L6-v2 (same encoder as production).
  bge-m3   — BAAI/bge-m3, raw text both sides (no prefixes).
  e5base   — intfloat/multilingual-e5-base, "passage: "/"query: " prefixes.

For every model, queries embedded twice: raw Vietnamese (vi) and LLM-English
(en). Doc embeddings stored fp16; query embeddings fp32.

Outputs per model dir investigations/vi_retrieval/emb_<model>/:
  doc_vectors.npy (N x D fp16), item_ids.json, q_vi.npy, q_en.npy, meta.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
FULL_VEC = ROOT / "experiments/embedding_builds/multi_domain_full"

MODELS = {
    "minilm": {"hf": "sentence-transformers/all-MiniLM-L6-v2", "doc_prefix": "", "q_prefix": ""},
    "bge-m3": {"hf": "BAAI/bge-m3", "doc_prefix": "", "q_prefix": ""},
    "e5base": {"hf": "intfloat/multilingual-e5-base", "doc_prefix": "passage: ", "q_prefix": "query: "},
}
DOC_BATCH = 256
Q_BATCH = 64


def load_queries() -> pd.DataFrame:
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
        rows.append({"item_id": q["item_id"], "vi_query": q["vi_query"], "en_query": tr.get(q["item_id"], "")})
    df = pd.DataFrame(rows)
    print(f"queries: {len(df)} ({df['en_query'].ne('').sum()} translated)", flush=True)
    return df


def encode_st(model, texts: list[str], batch: int, desc: str,
              ckpt_path: str | None = None) -> np.ndarray:
    out = np.empty((len(texts), model.get_sentence_embedding_dimension()), dtype=np.float32)
    start = 0
    if ckpt_path and Path(ckpt_path).exists():
        prev = np.load(ckpt_path)
        n = min(len(prev), len(texts))
        out[:n] = prev[:n]
        start = n
        print(f"    {desc}: resuming at {start}/{len(texts)}", flush=True)
    t0 = time.time()
    for i in range(start, len(texts), batch):
        emb = model.encode(texts[i:i + batch], batch_size=batch,
                           convert_to_numpy=True, normalize_embeddings=True,
                           show_progress_bar=False)
        out[i:i + len(emb)] = emb
        if ckpt_path and (i // batch) % 50 == 0:
            np.save(ckpt_path, out[:i + len(emb)])
        if (i // batch) % 50 == 0:
            print(f"    {desc} {i + len(emb)}/{len(texts)} ({time.time()-t0:.0f}s)", flush=True)
    print(f"    {desc} done {len(texts)} in {time.time()-t0:.0f}s", flush=True)
    if ckpt_path:
        Path(ckpt_path).unlink(missing_ok=True)
    return out


def minilm_docs(universe_ids: list[str]) -> tuple[np.ndarray, list[str]]:
    """Gather universe rows from the full-catalog MiniLM artifact."""
    vecs = np.load(FULL_VEC / "vectors.npy", mmap_mode="r")
    ids = np.load(FULL_VEC / "item_ids.npy", mmap_mode="r")
    id2row = {str(i): r for r, i in enumerate(ids)}
    rows = np.array([id2row[i] for i in universe_ids], dtype=np.int64)
    print(f"minilm: gathered {len(rows)} rows", flush=True)
    return np.asarray(vecs[rows], dtype=np.float16), universe_ids


def main() -> None:
    uitems = pd.read_parquet(OUT / "universe_items.parquet")
    universe_ids = uitems["item_id"].tolist()
    queries = load_queries()

    def get_model(name: str, cfg: dict):
        from sentence_transformers import SentenceTransformer
        import torch
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.set_float32_matmul_precision("high")
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        model = SentenceTransformer(cfg["hf"], device=dev)
        if name != "minilm":
            model = model.half()  # fp16: ~2x on this GPU, verified embeddings stable
        return model, dev

    # pass 1: document vectors for every model (queries encoded in pass 2 so
    # late-arriving translations are not baked into the cache)
    for name, cfg in MODELS.items():
        mdir = OUT / f"emb_{name}"
        mdir.mkdir(exist_ok=True)
        dv_path = mdir / "doc_vectors.npy"
        meta_path = mdir / "meta.json"

        if name == "minilm":
            dv, _ = minilm_docs(universe_ids)
            np.save(dv_path, dv)
            meta = {"model": cfg["hf"], "source": "full_catalog_artifact_rows", "dim": int(dv.shape[1])}
            meta_path.write_text(json.dumps(meta))
        elif dv_path.exists() and meta_path.exists():
            print(f"{name}: docs cached, skipping encode", flush=True)
        else:
            model, dev = get_model(name, cfg)
            texts = [cfg["doc_prefix"] + t for t in uitems["doc_text"].tolist()]
            print(f"{name}: encoding {len(texts)} docs on {dev} ...", flush=True)
            dv = encode_st(model, texts, DOC_BATCH, f"{name}-docs",
                           ckpt_path=str(mdir / "doc_vectors.ckpt.npy")).astype(np.float16)
            np.save(dv_path, dv)
            meta = {"model": cfg["hf"], "dim": int(dv.shape[1]), "doc_prefix": cfg["doc_prefix"]}
            meta_path.write_text(json.dumps(meta))
            del model
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        (mdir / "item_ids.json").write_text(json.dumps(universe_ids))
        print(f"{name}: docs done -> {mdir}", flush=True)

    # pass 2: query vectors (vi raw + en translated) — reload queries so
    # translations produced during pass-1 doc encoding are included
    queries = load_queries()
    for name, cfg in MODELS.items():
        mdir = OUT / f"emb_{name}"
        qvi_path, qen_path = mdir / "q_vi.npy", mdir / "q_en.npy"
        if qvi_path.exists() and qen_path.exists():
            print(f"{name}: queries cached", flush=True)
            continue
        model, dev = get_model(name, cfg)
        vi_texts = queries["vi_query"].tolist()
        en_texts = [(cfg["q_prefix"] + q if q else "") for q in queries["en_query"].tolist()]
        n_missing = sum(1 for q in queries["en_query"] if not q)
        print(f"{name}: encoding queries ({n_missing} missing EN) on {dev} ...", flush=True)
        qvi = encode_st(model, [cfg["q_prefix"] + t for t in vi_texts], Q_BATCH, f"{name}-qvi")
        qen = encode_st(model, en_texts, Q_BATCH, f"{name}-qen")
        np.save(qvi_path, qvi)
        np.save(qen_path, qen)
        del model
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        qdf = queries[["item_id"]].copy()
        qdf.to_parquet(mdir / "query_items.parquet", index=False)
        print(f"{name}: queries done", flush=True)


if __name__ == "__main__":
    main()
