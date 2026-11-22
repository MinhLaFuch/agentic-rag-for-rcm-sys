"""Build and persist a verified FAISS HNSW index (e.g. hnsw_sq8) from a full embedding artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from package.embeddings.vector_store import VectorStore
from package.utils import ensure_utf8_stdout


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_and_save_ann_index(
    embeddings_dir: Path,
    output_dir: Path,
    *,
    kind: str = "hnsw_sq8",
    m: int = 32,
    ef_search: int = 1024,
    train_size: int = 262144,
    seed: int = 42,
) -> dict:
    import faiss

    emb_dir = Path(embeddings_dir).resolve()
    emb_manifest_path = emb_dir / "manifest.json"
    if not emb_manifest_path.exists():
        raise FileNotFoundError(f"Embedding artifact missing manifest.json: {emb_dir}")
    emb_manifest = json.loads(emb_manifest_path.read_text(encoding="utf-8"))
    store = VectorStore.load(emb_dir)

    t0 = time.perf_counter()
    rng = np.random.default_rng(seed)
    print(f"[ann-build] building {kind} (m={m}, ef_search={ef_search}) on {len(store):,} x {store.dimension}", flush=True)
    if kind == "hnsw_flat":
        index = faiss.IndexHNSWFlat(store.dimension, m, faiss.METRIC_INNER_PRODUCT)
    elif kind in ("hnsw_sq8", "hnsw_fp16"):
        qtype = faiss.ScalarQuantizer.QT_8bit if kind == "hnsw_sq8" else faiss.ScalarQuantizer.QT_fp16
        index = faiss.IndexHNSWSQ(store.dimension, qtype, m, faiss.METRIC_INNER_PRODUCT)
        size = min(len(store.item_ids), train_size)
        sample = np.sort(rng.choice(len(store.item_ids), size=size, replace=False))
        print(f"[ann-build] training quantizer on {size:,} sampled vectors...", flush=True)
        index.train(np.ascontiguousarray(store.embeddings[sample], dtype=np.float32))
    else:
        raise ValueError(f"Unsupported ANN index: {kind}")

    print(f"[ann-build] adding {len(store):,} vectors...", flush=True)
    index.add(store.embeddings)
    index.hnsw.efSearch = ef_search
    build_seconds = time.perf_counter() - t0

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    index_path = out / "index.faiss"
    print(f"[ann-build] writing {index_path} ...", flush=True)
    faiss.write_index(index, str(index_path))
    index_sha = _sha256_file(index_path)

    manifest = {
        "format": "faiss_ann_index_v1",
        "status": "complete",
        "index": kind,
        "m": m,
        "ef_search": ef_search,
        "train_size": train_size,
        "seed": seed,
        "num_items": int(len(store.item_ids)),
        "dimension": int(store.dimension),
        "faiss_version": faiss.__version__,
        "embeddings_dir": str(emb_dir),
        "embedding_build_id": emb_manifest.get("build_id"),
        "embedding_manifest_sha256": _sha256_file(emb_manifest_path),
        "index_file": "index.faiss",
        "index_sha256": index_sha,
        "build_seconds": build_seconds,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[ann-build] complete in {build_seconds:.1f}s -> {out} ({index_path.stat().st_size / 2**20:.1f} MiB)", flush=True)
    return manifest


def main() -> None:
    ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--embeddings-path", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--index", choices=("hnsw_flat", "hnsw_sq8", "hnsw_fp16"), default="hnsw_sq8")
    ap.add_argument("--m", type=int, default=32)
    ap.add_argument("--ef-search", type=int, default=1024)
    ap.add_argument("--train-size", type=int, default=262144)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    build_and_save_ann_index(
        args.embeddings_path,
        args.output,
        kind=args.index,
        m=args.m,
        ef_search=args.ef_search,
        train_size=args.train_size,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
