"""Diagnose WHY category_oracle recall@200 is only ~10% (exp_003 probe).

For each user sampled in an experiment's config.yaml (sampled_user_ids), rebuild
the exact oracle query (main_category + categories of held-out target items,
column 1 of item_text_tables), then measure per-target:

  - catalog_visible: item present in the policy-filtered corpus `items` table
  - bm25_rank:       rank in SearchTool(BM25-only) at limit=1000 (-1 = absent)
  - dense_rank:      rank in raw vector_store.search at k=1000 (-1 = absent)
  - hybrid_rank:     rank in SearchTool(vector_store + rrf) at limit=1000

Aggregates: visibility ceiling, per-leg recall@{50,200,500,1000}, rank histogram.

Usage (from src/):
    python scripts/evaluation/oracle_recall_diagnostic.py <exp_dir>
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "evaluation"))
from candidate_recall import item_text_tables, normalize_query_text  # noqa: E402

from package.config import load_config
from package.config.resolve_bundle_paths import resolve_bundle_paths
from package.data.mapping import load_mappings
from package.data.split import load_splits
from package.evaluation.recommender.config import select_fit_target
from package.tools import SearchTool, ToolCallLogger

RANK_K = 1000
RECALL_KS = (50, 200, 500, 1000)


def _load_jsonl(path: Path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("exp_dir", type=Path, help="e.g. experiments/candidate_recall/exp_003")
    args = ap.parse_args()

    cfg = yaml.safe_load((args.exp_dir / "config.yaml").read_text(encoding="utf-8"))
    sampled = cfg["config"]["sampled_user_ids"]  # {seg: [user_idx,...]}
    emb_prov = cfg["config"].get("embedding_provenance") or {}

    t0 = time.time()
    data_paths = resolve_bundle_paths()
    train, val, test = load_splits(data_paths.splits_dir, ("user_idx", "item_idx", "timestamp"))
    fit_df, target_df = select_fit_target(train, val, test, "validation")
    user2id, item2id = load_mappings(data_paths.mapped_dir)
    id2item = {v: k for k, v in item2id.items()}
    num_users, num_items = len(user2id), len(item2id)
    target_by_user = target_df.groupby("user_idx")["item_idx"].apply(set).to_dict()
    print(f"loaded splits+mappings in {time.time()-t0:.0f}s", flush=True)

    # corpus: same load + temporal policy as candidate_recall.py
    from package.corpus import load_corpus
    from package.corpus.apply_metadata_policy import apply_metadata_policy
    t0 = time.time()
    eval_cfg = load_config("eval/candidate_recall")["candidate_recall"]
    from package.config import get_domains
    meta_files = [(d, str(data_paths.meta_path(d))) for d in get_domains()]
    corpus, coverage = load_corpus(
        data_paths.corpus_path, meta_files, item2id,
        float(eval_cfg["min_metadata_coverage"]),
        allow_missing_sources=bool(eval_cfg.get("allow_missing_corpus_sources")))
    metadata_policy = apply_metadata_policy(
        corpus, str(eval_cfg["metadata_policy"]),
        as_of_timestamp=int(target_df.timestamp.min()))
    print(f"corpus loaded in {time.time()-t0:.0f}s coverage={coverage:.3f} "
          f"policy={eval_cfg['metadata_policy']}", flush=True)

    item_text = item_text_tables(corpus, any("::" in k for k in list(item2id)[:1000]))

    # search tools
    search_bm25 = SearchTool(corpus, logger=ToolCallLogger())
    search_hybrid = None
    vector_store = None
    query_encoder = None
    emb_path = Path(emb_prov.get("artifact_dir") or emb_prov.get("path") or "")
    # fall back to the known artifact used by exp_003
    if not emb_path.exists():
        emb_path = data_paths.experiments_dir / "embedding_builds" / "multi_domain_full"
    from scripts.data_pipeline.build_item_embeddings import load_validated_embeddings
    from package.embeddings import TextEncoder
    vector_store, encoder_impl, _ = load_validated_embeddings(
        emb_path, data_paths.corpus_path)
    query_encoder = TextEncoder(encoder_impl.encode, dimension=vector_store.dimension)
    search_hybrid = SearchTool(
        corpus, logger=ToolCallLogger(), vector_store=vector_store,
        query_encoder=query_encoder, rrf_k=60)
    print(f"hybrid ready: {len(vector_store):,} vectors", flush=True)

    # per-user evaluation
    per_target = []  # dicts
    users_done = 0
    for seg, ulist in sampled.items():
        for u in ulist:
            targets = target_by_user.get(u)
            if not targets:
                continue
            users_done += 1
            query_ids = [id2item[i] for i in targets if i in id2item]
            text_by_id = item_text(query_ids)
            column = 1  # category_oracle
            query = " ".join(text_by_id[i][column] for i in query_ids if i in text_by_id)
            query = normalize_query_text(query, "raw")
            n_tokens = len(query.split())

            # BM25 leg
            bm25_rank = {}
            if query.strip():
                res = search_bm25(query=query, limit=RANK_K)
                for rank, c in enumerate(res.data.get("candidates", []), 1):
                    iid = c.get("item_id") or c.get("original_item_id")
                    bm25_rank[iid] = rank
                search_bm25.logger.records.clear()

            # dense leg (raw vector search)
            dense_rank = {}
            if query.strip():
                enc = query_encoder.encode([query])
                hits = vector_store.search(np.asarray(enc)[0], RANK_K)
                for rank, (iid, _s) in enumerate(hits, 1):
                    dense_rank[iid] = rank

            # hybrid fused
            hyb_rank = {}
            if query.strip():
                res = search_hybrid(query=query, limit=RANK_K)
                for rank, c in enumerate(res.data.get("candidates", []), 1):
                    iid = c.get("item_id") or c.get("original_item_id")
                    hyb_rank[iid] = rank
                search_hybrid.logger.records.clear()

            # visibility: item in corpus items table
            target_namespaced = [id2item[i] for i in targets if i in id2item]
            visible = set()
            if target_namespaced:
                marks = ",".join("?" for _ in target_namespaced)
                rows, _ = corpus.select(
                    f"SELECT item_id FROM items WHERE item_id IN ({marks})",
                    target_namespaced, max_rows=len(target_namespaced))
                visible = {r["item_id"] for r in rows}

            for i in targets:
                if i not in id2item:
                    continue
                ns = id2item[i]
                per_target.append({
                    "user_idx": u, "seg": seg, "item_idx": i, "item_id": ns,
                    "visible": ns in visible,
                    "bm25_rank": bm25_rank.get(ns),
                    "dense_rank": dense_rank.get(ns),
                    "hybrid_rank": hyb_rank.get(ns),
                    "query_tokens": n_tokens,
                })
            if users_done % 10 == 0:
                print(f"  {users_done} users, {len(per_target)} targets", flush=True)

    # aggregate
    n = len(per_target)
    vis = [t for t in per_target if t["visible"]]
    print(f"\ntargets={n} users={users_done} catalog_visible={len(vis)} ({len(vis)/n:.3f})")

    def recall(recs, key):
        out = {}
        for k in RECALL_KS:
            hit = sum(1 for t in recs if t[key] is not None and t[key] <= k)
            out[f"recall@{k}"] = round(hit / len(recs), 4) if recs else None
        return out

    report = {
        "exp_dir": str(args.exp_dir),
        "n_targets": n, "n_users": users_done,
        "catalog_visible_frac": round(len(vis) / n, 4) if n else None,
        "invisible_targets": n - len(vis),
        "all_targets": {
            "bm25": recall(per_target, "bm25_rank"),
            "dense": recall(per_target, "dense_rank"),
            "hybrid": recall(per_target, "hybrid_rank"),
        },
        "visible_only": {
            "bm25": recall(vis, "bm25_rank"),
            "dense": recall(vis, "dense_rank"),
            "hybrid": recall(vis, "hybrid_rank"),
        },
        "query_token_stats": {
            "mean": float(np.mean([t["query_tokens"] for t in per_target])) if per_target else None,
            "p90": float(np.percentile([t["query_tokens"] for t in per_target], 90)) if per_target else None,
            "max": max((t["query_tokens"] for t in per_target), default=None),
        },
        "rank_buckets": {},
    }
    for key in ("bm25_rank", "dense_rank", "hybrid_rank"):
        buckets = Counter()
        for t in vis:
            r = t[key]
            if r is None:
                buckets[">1000"] += 1
            elif r <= 50:
                buckets["<=50"] += 1
            elif r <= 200:
                buckets["51-200"] += 1
            elif r <= 500:
                buckets["201-500"] += 1
            else:
                buckets["501-1000"] += 1
        report["rank_buckets"][key] = dict(buckets)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    out = args.exp_dir / "oracle_recall_diagnostic.json"
    out.write_text(json.dumps({"report": report, "targets": per_target}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
