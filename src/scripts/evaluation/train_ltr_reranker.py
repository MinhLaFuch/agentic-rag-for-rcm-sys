"""Train and persist a MultiSignalReranker on a completed frozen validation retrieval matrix.

Evaluates out-of-fold 5-fold user-grouped CV (no user leakage) against BaselineScorer and
HybridScorer(w=4.0) before fitting the final artifact on the full training matrix cohort.
Never train on held-out test splits.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import time

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from package.config.resolve_bundle_paths import resolve_bundle_paths
from package.data.mapping import load_mappings
from package.data.split import load_splits
from package.evaluation.recommender.analysis.build_core_model import build_core_model
from package.evaluation.recommender.config import select_fit_target
from package.recommenders.shared import file_hash
from package.tools.retrieval.domain_category_popularity import DomainCategoryPopularity
from package.tools.scoring import BaselineScorer, HybridScorer, MultiSignalReranker
from package.utils import ensure_utf8_stdout


def _ndcg_at_k(ranked: list[str], gt: set[str], k: int = 10) -> float:
    if not gt:
        return 0.0
    hits = [int(x in gt) for x in ranked[:k]]
    dcg = sum(v / np.log2(i + 2) for i, v in enumerate(hits))
    ideal = sum(1.0 / np.log2(i + 2) for i in range(min(k, len(gt))))
    return float(dcg / ideal) if ideal > 0 else 0.0


def _make_estimator(kind: str, seed: int):
    if kind == "hist_gbdt":
        return HistGradientBoostingClassifier(
            max_depth=3,
            learning_rate=0.05,
            max_iter=100,
            min_samples_leaf=30,
            l2_regularization=5.0,
            random_state=seed,
        )
    if kind == "logreg":
        return make_pipeline(StandardScaler(), LogisticRegression(C=0.2, class_weight="balanced", max_iter=500))
    raise ValueError(f"Unsupported estimator kind: {kind}")


def main() -> None:
    ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--matrix-dir", type=Path, required=True, help="Completed frozen validation retrieval matrix")
    ap.add_argument("--output", type=Path, required=True, help="Output directory for persisted reranker artifact")
    ap.add_argument("--mode", default="recency_weighted")
    ap.add_argument("--budget", type=int, default=100)
    ap.add_argument("--pool", default="fused")
    ap.add_argument("--model", choices=("hist_gbdt", "logreg"), default="hist_gbdt")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    t0 = time.perf_counter()
    matrix_dir = args.matrix_dir.resolve()
    completion = json.loads((matrix_dir / "artifact_hashes.json").read_text(encoding="utf-8"))
    if completion.get("status") != "complete":
        raise ValueError(f"Matrix is not complete: {matrix_dir}")
    for name in ("config.json", "candidate_sets.jsonl", "frozen.json"):
        if file_hash(matrix_dir / name) != completion["hashes"][name]:
            raise ValueError(f"Matrix checksum mismatch: {name}")
    matrix_cfg = json.loads((matrix_dir / "config.json").read_text(encoding="utf-8"))
    eval_on = matrix_cfg["provenance"]["protocol"]["item_knn"]["eval_on"]
    if eval_on != "validation":
        raise ValueError(f"Refusing to train reranker on split={eval_on!r}; validation only")

    paths = resolve_bundle_paths(tag=args.tag)
    train, val, test = load_splits(paths.splits_dir, ("user_idx", "item_idx", "timestamp"))
    fit_df, _ = select_fit_target(train, val, test, "validation")
    user2id, item2id = load_mappings(paths.mapped_dir)
    id2item = {v: k for k, v in item2id.items()}
    knn = build_core_model(paths, "validation", 20, fit_df, user2id, item2id)
    base_scorer = BaselineScorer(knn)
    hybrid_scorer = HybridScorer(knn, popularity_weight=4.0)

    cutoff = int(matrix_cfg["provenance"]["protocol"]["metadata_policy"]["as_of_timestamp"])
    conn = sqlite3.connect(f"file:{paths.corpus_path.resolve()}?mode=ro", uri=True)
    item_dom, item_mcat = {}, {}
    for iid, dom, mcat, fts in conn.execute("SELECT item_id, domain, main_category, first_seen_ts FROM items"):
        if fts is not None and fts <= cutoff:
            if dom:
                item_dom[str(iid)] = str(dom)
            if mcat:
                item_mcat[str(iid)] = str(mcat)
    conn.close()
    dcp = DomainCategoryPopularity(item_dom, item_mcat, {}, {})
    extractor = MultiSignalReranker(base_scorer, None, id2item=id2item, domain_pop=dcp)

    X_list, y_list, meta_list = [], [], []
    with (matrix_dir / "candidate_sets.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["mode"] != args.mode or row["budget"] != args.budget:
                continue
            gt = set(row["targets"])
            cands = row["pools"].get(args.pool, [])
            if not gt or not cands:
                continue
            u = int(row["user_idx"])
            seg = str(row["segment"])
            idxs = np.array([item2id[i] for i in cands], dtype=np.int64)
            attr = {x["item_id"]: x for x in (row.get("source_evidence") or [])}
            req = extractor.for_request(source_attribution=attr, seen_items=row.get("seen", []))
            feats = req.extract_features(u, idxs)
            labels = np.array([1 if i in gt else 0 for i in cands], dtype=np.int32)
            X_list.append(feats)
            y_list.append(labels)
            meta_list.append((u, seg, cands, gt, idxs))

    print(f"[ltr-train] extracted {len(X_list)} users, positives={sum(int(y.sum()) for y in y_list)} in {time.perf_counter()-t0:.1f}s", flush=True)
    kf = KFold(n_splits=args.folds, shuffle=True, random_state=args.seed)
    oof_scores = [None] * len(meta_list)
    for tr_idx, va_idx in kf.split(meta_list):
        X_tr = np.vstack([X_list[i] for i in tr_idx])
        y_tr = np.concatenate([y_list[i] for i in tr_idx])
        est = _make_estimator(args.model, args.seed)
        est.fit(X_tr, y_tr)
        for i in va_idx:
            oof_scores[i] = est.predict_proba(X_list[i])[:, 1]

    def summarize(label, preds_list):
        by_seg = {"all": [], "cold": [], "sparse": [], "warm": []}
        hits = {"all": 0, "cold": 0, "sparse": 0, "warm": 0}
        for (u, seg, cands, gt, idxs), sc in zip(meta_list, preds_list):
            order = np.lexsort((np.asarray(cands), -np.asarray(sc)))
            ranked = [cands[i] for i in order]
            val_n = _ndcg_at_k(ranked, gt, 10)
            by_seg["all"].append(val_n)
            by_seg[seg].append(val_n)
            if any(x in gt for x in ranked[:10]):
                hits["all"] += 1
                hits[seg] += 1
        out = {s: {"ndcg10": float(np.mean(by_seg[s])) if by_seg[s] else 0.0, "hits10": hits[s]} for s in by_seg}
        print(f"  {label:20s}: all={out['all']['ndcg10']:.5f}({out['all']['hits10']}) "
              f"cold={out['cold']['ndcg10']:.5f}({out['cold']['hits10']}) "
              f"sparse={out['sparse']['ndcg10']:.5f}({out['sparse']['hits10']}) "
              f"warm={out['warm']['ndcg10']:.5f}({out['warm']['hits10']})", flush=True)
        return out

    cv_report = {
        "baseline": summarize("baseline", [base_scorer.score(u, idxs) for u, _, _, _, idxs in meta_list]),
        "hybrid_w4": summarize("hybrid_w4", [hybrid_scorer.score(u, idxs) for u, _, _, _, idxs in meta_list]),
        f"oof_{args.model}": summarize(f"oof_{args.model}", oof_scores),
    }

    final_est = _make_estimator(args.model, args.seed)
    final_est.fit(np.vstack(X_list), np.concatenate(y_list))
    manifest = MultiSignalReranker.save_estimator(
        final_est,
        args.output,
        metadata={
            "tag": args.tag,
            "model_kind": args.model,
            "seed": args.seed,
            "train_matrix_dir": str(matrix_dir),
            "train_matrix_sha256": completion["hashes"]["candidate_sets.jsonl"],
            "train_users": [u for u, *_ in meta_list],
            "mode": args.mode,
            "budget": args.budget,
            "pool": args.pool,
            "cv_folds": args.folds,
            "cv_report": cv_report,
        },
    )
    print(f"[ltr-train] saved verified reranker -> {args.output} ({manifest['checksums']['reranker.pkl'][:12]})", flush=True)


if __name__ == "__main__":
    main()
