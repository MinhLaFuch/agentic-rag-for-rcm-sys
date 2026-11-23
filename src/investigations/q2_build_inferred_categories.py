"""Q2 build: assign categories to uncategorized items via embedding kNN vote.

For every catalog item with NO item_categories rows (~230k), find its K nearest
categorized neighbors (existing all-MiniLM-L6-v2 doc vectors, unit-norm) and
assign the similarity-weighted top category. Prototype validation
(q2_categorization_proto.json): top-1 category recovers a true category ~99%
of the time on held-out categorized items.

Resumable: processes uncategorized items in batches of BATCH queries; each
batch writes its own parquet part under OUT_DIR. Re-running skips parts that
already exist. Merge parts afterwards into the final artifact consumed by
apply_metadata_policy(inferred_categories=...).

Output parts: investigations/q2_inferred_cats/part_XXXXX.parquet
Columns: item_id, category, vote_share, top_score, n_neighbors
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import torch
    _HAS_TORCH = True
except ImportError:
    _HAS_TORCH = False

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "resource/corpus/multi_domain/corpus_multi_domain.sqlite"
VEC_DIR = ROOT / "experiments/embedding_builds/multi_domain_semantic"
OUT_DIR = Path(__file__).parent / "q2_inferred_cats"

K = 10
REF_CHUNK = 200_000
Q_BATCH = 1024
BATCH = 10_000
SEED = 42

# Device-flexible: CUDA when torch+CUDA are available and the fp16 reference
# matrix (~1.9GB for 2.4M x 384) fits VRAM; otherwise the NumPy CPU path.
DEVICE = "cuda" if (_HAS_TORCH and torch.cuda.is_available()) else "cpu"
GPU_REF_CHUNK = 200_000   # rows of V_ref per similarity block
GPU_Q_BATCH = 2048        # queries per block -> S ~800MB fp16


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)

    conn = sqlite3.connect(f"file:{CORPUS}?mode=ro", uri=True)
    catmap: dict[str, list[str]] = defaultdict(list)
    for iid, cat in conn.execute("SELECT item_id, category FROM item_categories"):
        catmap[iid].append(cat)
    conn.close()
    print(f"categorized items: {len(catmap)}", flush=True)

    item_ids = json.loads((VEC_DIR / "item_ids.json").read_text(encoding="utf-8"))
    id2row = {iid: i for i, iid in enumerate(item_ids)}
    uncategorized_ids = np.array([iid for iid in item_ids if iid not in catmap])
    ref_rows = np.array(sorted(id2row[i] for i in catmap if i in id2row), dtype=np.int64)
    print(f"uncategorized: {len(uncategorized_ids)}  reference: {len(ref_rows)}", flush=True)

    vecs = np.load(VEC_DIR / "vectors.npy", mmap_mode="r")
    n_batches = (len(uncategorized_ids) + BATCH - 1) // BATCH
    print(f"device={DEVICE}", flush=True)

    # CUDA path: stage the whole categorized reference on GPU once (fp16,
    # ~1.9GB) instead of re-reading memmap chunks per batch.
    V_ref_gpu = None
    ref_rows_gpu = None
    if DEVICE == "cuda":
        chunks = []
        for r0 in range(0, len(ref_rows), REF_CHUNK):
            rc = ref_rows[r0:r0 + REF_CHUNK]
            arr = np.asarray(vecs[rc], dtype=np.float32)
            chunks.append(torch.from_numpy(arr).to("cuda", dtype=torch.float16))
        V_ref_gpu = torch.cat(chunks)
        del chunks
        ref_rows_gpu = torch.from_numpy(ref_rows).to("cuda")
        print(f"reference staged on GPU: {tuple(V_ref_gpu.shape)} fp16", flush=True)

    for b in range(n_batches):
        part_path = OUT_DIR / f"part_{b:05d}.parquet"
        if part_path.exists():
            print(f"batch {b + 1}/{n_batches}: exists, skip", flush=True)
            continue
        ids = uncategorized_ids[b * BATCH:(b + 1) * BATCH]
        qrows = np.array([id2row[i] for i in ids], dtype=np.int64)
        nq = len(qrows)

        if DEVICE == "cuda":
            Q = torch.from_numpy(
                np.asarray(vecs[qrows], dtype=np.float32)
            ).to("cuda", dtype=torch.float16)
            best_scores = torch.full((nq, K), -float("inf"), device="cuda")
            best_rows = torch.full((nq, K), -1, device="cuda", dtype=torch.int64)
            for r0 in range(0, V_ref_gpu.shape[0], GPU_REF_CHUNK):
                Vc = V_ref_gpu[r0:r0 + GPU_REF_CHUNK]
                rc = ref_rows_gpu[r0:r0 + GPU_REF_CHUNK]
                for q0 in range(0, nq, GPU_Q_BATCH):
                    S = Q[q0:q0 + GPU_Q_BATCH] @ Vc.T
                    k = min(K, S.shape[1])
                    s, i = torch.topk(S, k, dim=1)
                    all_s = torch.cat([best_scores[q0:q0 + GPU_Q_BATCH], s], dim=1)
                    all_r = torch.cat([best_rows[q0:q0 + GPU_Q_BATCH], rc[i]], dim=1)
                    ms, mi = torch.topk(all_s, K, dim=1)
                    best_scores[q0:q0 + GPU_Q_BATCH] = ms
                    best_rows[q0:q0 + GPU_Q_BATCH] = torch.gather(all_r, 1, mi)
            best_scores = best_scores.float().cpu().numpy()
            best_rows = best_rows.cpu().numpy()
        else:
            Q = np.asarray(vecs[qrows], dtype=np.float32)
            best_scores = np.full((nq, K), -np.inf, dtype=np.float32)
            best_rows = np.full((nq, K), -1, dtype=np.int64)
            for r0 in range(0, len(ref_rows), REF_CHUNK):
                ref_chunk_rows = ref_rows[r0:r0 + REF_CHUNK]
                Vc = np.asarray(vecs[ref_chunk_rows], dtype=np.float32)
                for q0 in range(0, nq, Q_BATCH):
                    S = Q[q0:q0 + Q_BATCH] @ Vc.T
                    k = min(K, S.shape[1])
                    part = np.argpartition(-S, k - 1, axis=1)[:, :k]
                    ps = np.take_along_axis(S, part, axis=1)
                    all_s = np.concatenate([best_scores[q0:q0 + Q_BATCH], ps], axis=1)
                    all_r = np.concatenate([best_rows[q0:q0 + Q_BATCH],
                                            ref_chunk_rows[part]], axis=1)
                    order = np.argsort(-all_s, axis=1)[:, :K]
                    best_scores[q0:q0 + Q_BATCH] = np.take_along_axis(all_s, order, axis=1)
                    best_rows[q0:q0 + Q_BATCH] = np.take_along_axis(all_r, order, axis=1)

        rows = []
        for qi, iid in enumerate(ids):
            votes: dict[str, float] = defaultdict(float)
            for s, rr in zip(best_scores[qi], best_rows[qi]):
                if rr < 0:
                    continue
                w = float(max(s, 0.0))
                for cat in catmap.get(item_ids[int(rr)], []):
                    votes[cat] += w
            if not votes:
                continue
            ranked = sorted(votes.items(), key=lambda kv: -kv[1])
            total = sum(v for _, v in ranked)
            rows.append({
                "item_id": iid,
                "category": ranked[0][0],
                "vote_share": ranked[0][1] / total if total else 0.0,
                "top_score": float(best_scores[qi, 0]),
                "n_neighbors": int((best_rows[qi] >= 0).sum()),
            })
        pd.DataFrame(rows).to_parquet(part_path, index=False)
        print(f"batch {b + 1}/{n_batches}: {len(rows)} assignments -> {part_path.name}", flush=True)

    print("done — merge parts into the final artifact", flush=True)


if __name__ == "__main__":
    main()
