"""Q2 prototype: can embedding kNN assign categories to uncategorized items?

Validates the categorization-layer approach offline before any pipeline change:

  1. categorized items = distinct item_id in corpus item_categories
     (~2.41M of 2.64M; ~230k items have NO category rows — the tail).
  2. Hold out 6000 categorized items, pretend they are uncategorized, and check
     whether kNN-vote over the remaining categorized items recovers their true
     categories (any-hit / level-wise hit).
  3. Apply the same procedure to 6000 truly-uncategorized items and report the
     confidence distribution (can we trust assignments?).

Uses the existing all-MiniLM-L6-v2 doc vectors (unit-norm -> dot = cosine).
Chunked matmul keeps RAM ~1GB; memmap avoids loading the 3.8GB matrix.

Output: investigations/q2_categorization_proto.json
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "resource/corpus/multi_domain/corpus_multi_domain.sqlite"
VEC_DIR = ROOT / "experiments/embedding_builds/multi_domain_semantic"
OUT = Path(__file__).parent / "q2_categorization_proto.json"

N_HOLDOUT = 6000
N_UNCAT = 6000
K = 10
REF_CHUNK = 200_000
Q_BATCH = 1024
SEED = 42


def cat_levels(cat: str) -> list[str]:
    """Category string -> [full, level1, level2, ...] prefix keys."""
    parts = [p.strip() for p in cat.split(">")]
    return [">".join(parts[:i]).strip() for i in range(1, len(parts) + 1)]


def main() -> None:
    # ---- catalog categories -------------------------------------------------
    conn = sqlite3.connect(f"file:{CORPUS}?mode=ro", uri=True)
    catmap: dict[str, list[str]] = defaultdict(list)
    for iid, cat in conn.execute("SELECT item_id, category FROM item_categories"):
        catmap[iid].append(cat)
    conn.close()
    print(f"categorized items: {len(catmap)}", flush=True)

    item_ids = json.loads((VEC_DIR / "item_ids.json").read_text(encoding="utf-8"))
    id2row = {iid: i for i, iid in enumerate(item_ids)}
    cat_rows = {id2row[i]: cats for i, cats in catmap.items() if i in id2row}
    uncategorized_ids = [iid for iid in item_ids if iid not in catmap]
    print(f"uncategorized items: {len(uncategorized_ids)}", flush=True)

    rng = np.random.default_rng(SEED)
    cat_ids = np.array(sorted(cat_rows))
    holdout_rows = set(rng.choice(cat_ids, size=min(N_HOLDOUT, len(cat_ids)), replace=False).tolist())
    ref_rows = np.array([r for r in cat_ids if r not in holdout_rows], dtype=np.int64)
    uncat_rows = np.array(
        [id2row[i] for i in rng.choice(uncategorized_ids, size=min(N_UNCAT, len(uncategorized_ids)), replace=False)],
        dtype=np.int64,
    )
    query_rows = np.array(sorted(holdout_rows) + uncat_rows.tolist(), dtype=np.int64)
    n_holdout_q = len(holdout_rows)
    print(f"queries: {len(query_rows)} (holdout {n_holdout_q} + uncat {len(uncat_rows)}); "
          f"reference: {len(ref_rows)}", flush=True)

    vecs = np.load(VEC_DIR / "vectors.npy", mmap_mode="r")
    Q = np.asarray(vecs[query_rows], dtype=np.float32)  # (nq, 384), unit-norm
    nq = len(query_rows)

    # ---- blocked top-k ------------------------------------------------------
    best_scores = np.full((nq, K), -np.inf, dtype=np.float32)
    best_rows = np.full((nq, K), -1, dtype=np.int64)
    for r0 in range(0, len(ref_rows), REF_CHUNK):
        ref_chunk_rows = ref_rows[r0:r0 + REF_CHUNK]
        Vc = np.asarray(vecs[ref_chunk_rows], dtype=np.float32)
        for q0 in range(0, nq, Q_BATCH):
            S = Q[q0:q0 + Q_BATCH] @ Vc.T  # (qb, rc) cosine sims
            k = min(K, S.shape[1])
            part = np.argpartition(-S, k - 1, axis=1)[:, :k]
            ps = np.take_along_axis(S, part, axis=1)
            # merge with running top-k
            all_s = np.concatenate([best_scores[q0:q0 + Q_BATCH], ps], axis=1)
            all_r = np.concatenate([best_rows[q0:q0 + Q_BATCH],
                                    ref_chunk_rows[part]], axis=1)
            order = np.argsort(-all_s, axis=1)[:, :K]
            best_scores[q0:q0 + Q_BATCH] = np.take_along_axis(all_s, order, axis=1)
            best_rows[q0:q0 + Q_BATCH] = np.take_along_axis(all_r, order, axis=1)
        print(f"  ref chunk {r0 // REF_CHUNK + 1}: done", flush=True)

    # ---- category vote ------------------------------------------------------
    # weight = sim score (shifted positive); each neighbor contributes all its cats
    def predict(qi: int) -> dict[str, float]:
        votes: dict[str, float] = defaultdict(float)
        for s, rr in zip(best_scores[qi], best_rows[qi]):
            if rr < 0:
                continue
            w = float(max(s, 0.0))
            for cat in cat_rows.get(int(rr), []):
                votes[cat] += w
        return dict(votes)

    preds = [predict(i) for i in range(nq)]

    # ---- metrics on holdout --------------------------------------------------
    def levels_of(cats):
        out = set()
        for c in cats:
            out.update(cat_levels(c))
        return out

    stats = {"any_hit@1": 0, "any_hit@3": 0, "full_hit@1": 0, "n": 0,
             "level_hit": defaultdict(int), "level_tot": defaultdict(int)}
    for qi in range(n_holdout_q):
        true_cats = set(cat_rows[int(query_rows[qi])])
        true_levels = levels_of(true_cats)
        ranked = sorted(preds[qi].items(), key=lambda kv: -kv[1])
        pred_cats = [c for c, _ in ranked]
        pred_levels = levels_of(pred_cats[:3])
        stats["n"] += 1
        stats["any_hit@1"] += bool(set(pred_cats[:1]) & true_cats)
        stats["any_hit@3"] += bool(set(pred_cats[:3]) & true_cats)
        stats["full_hit@1"] += bool(set(pred_cats[:1]) == true_cats or
                                    (pred_cats and pred_cats[0] in true_cats and len(true_cats) == 1))
        for lv in true_levels:
            depth = lv.count(">")
            stats["level_tot"][depth] += 1
            stats["level_hit"][depth] += bool(lv in pred_levels)

    # ---- confidence on truly uncategorized ----------------------------------
    conf = []
    top_cat_dist = defaultdict(int)
    for qi in range(n_holdout_q, nq):
        ranked = sorted(preds[qi].items(), key=lambda kv: -kv[1])
        if not ranked:
            continue
        total = sum(v for _, v in ranked)
        top_share = ranked[0][1] / total if total else 0.0
        conf.append(top_share)
        top_cat_dist[ranked[0][0].split(">")[0].strip()] += 1
    conf = np.array(conf)

    out = {
        "n_holdout": n_holdout_q, "n_uncat": len(uncat_rows), "k": K,
        "reference_size": len(ref_rows),
        "holdout": {
            "any_hit@1": stats["any_hit@1"] / max(stats["n"], 1),
            "any_hit@3": stats["any_hit@3"] / max(stats["n"], 1),
            "exact_set@1": stats["full_hit@1"] / max(stats["n"], 1),
            "level_hit_rate": {str(d): stats["level_hit"][d] / max(stats["level_tot"][d], 1)
                               for d in sorted(stats["level_tot"])},
        },
        "uncategorized": {
            "top_vote_share": {
                "mean": float(conf.mean()), "p25": float(np.percentile(conf, 25)),
                "p50": float(np.percentile(conf, 50)), "p75": float(np.percentile(conf, 75)),
            },
            "frac_share_gt_0.5": float((conf > 0.5).mean()),
            "frac_share_gt_0.7": float((conf > 0.7).mean()),
            "top_level1_categories": dict(sorted(top_cat_dist.items(), key=lambda kv: -kv[1])[:15]),
        },
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out["holdout"], indent=2))
    print(json.dumps(out["uncategorized"]["top_vote_share"], indent=2))
    print("frac>0.5:", out["uncategorized"]["frac_share_gt_0.5"],
          "frac>0.7:", out["uncategorized"]["frac_share_gt_0.7"])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
