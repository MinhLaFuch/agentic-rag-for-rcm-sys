"""Track B benchmark: English natural-language cold-start queries (BM25 vs Dense ANN vs Hybrid RRF).

Builds a reproducible set of natural-language shopping queries from eligible validation target
items under two strict regimes:
  1. exact_title_paraphrase: natural shopping intent with store/brand tokens masked out
  2. lexical_drop_semantic: drops high-overlap lexical anchors (keeps category/domain + partial descriptors)
     to directly test vocabulary-mismatch recovery where pure BM25 struggles.

Never uses held-out test interactions; respects the exact historical_static_catalog eligibility mask.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sqlite3
import time

import numpy as np

from package.config.resolve_bundle_paths import resolve_bundle_paths
from package.data.mapping import load_mappings
from package.data.split import load_splits
from package.embeddings import SparseBM25Index, TextEncoder
from package.evaluation.recommender.config import select_fit_target
from package.tools.retrieval.fuse_candidates import fuse_candidates
from package.tools.retrieval.tokenize_search_query import tokenize_search_query
from package.utils import ensure_utf8_stdout
from scripts.data_pipeline.build_item_embeddings import load_validated_embeddings
from scripts.evaluation.ann_validation import build_ann_search

_TEMPLATES = (
    "looking for {desc} in {cat}",
    "recommend a reliable {desc} for {domain_label}",
    "need {desc} {cat} product",
    "best option for {desc} ({cat})",
)

_DOMAIN_LABELS = {
    "Electronics": "electronics and tech",
    "Video_Games": "video gaming",
    "Toys_and_Games": "toys and games",
}


def _clean_words(text: str) -> list[str]:
    return [w for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", text or "") if len(w) > 1]


def _build_natural_queries(
    corpus_path: Path,
    candidate_item_ids: list[str],
    *,
    cutoff: int,
    num_queries: int,
    seed: int,
) -> list[dict]:
    conn = sqlite3.connect(f"file:{corpus_path.resolve()}?mode=ro", uri=True)
    rng = np.random.default_rng(seed)
    shuffled = list(candidate_item_ids)
    rng.shuffle(shuffled)

    queries: list[dict] = []
    for start in range(0, len(shuffled), 500):
        if len(queries) >= num_queries:
            break
        chunk = shuffled[start:start + 500]
        marks = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"SELECT item_id, domain, title, store, main_category, first_seen_ts "
            f"FROM items WHERE item_id IN ({marks})",
            chunk,
        ).fetchall()
        for iid, dom, title, store, mcat, fts in rows:
            if len(queries) >= num_queries:
                break
            if fts is None or fts > cutoff or not title or not mcat:
                continue
            store_toks = {t.lower() for t in _clean_words(store or "")}
            title_words = [
                w for w in _clean_words(title)
                if w.lower() not in store_toks and not re.search(r"\d{3,}", w) and not w.isdigit()
            ]
            if len(title_words) < 5:
                continue
            # Natural intent query: mask brand/store & model numbers, keep 4-6 descriptive words + category context.
            desc_full = " ".join(title_words[1:6])
            # Harder vocabulary-mismatch query: drop first 2 lexical anchor words (brand/product line), keep tail descriptors + category.
            desc_hard = " ".join(title_words[3:7])
            if not tokenize_search_query(desc_full) or not tokenize_search_query(desc_hard):
                continue
            tmpl = _TEMPLATES[len(queries) % len(_TEMPLATES)]
            dom_label = _DOMAIN_LABELS.get(dom, dom.replace("_", " ").lower())
            q_natural = tmpl.format(desc=desc_full, cat=mcat, domain_label=dom_label)
            q_hard = tmpl.format(desc=desc_hard, cat=mcat, domain_label=dom_label)
            queries.append({
                "query_id": len(queries) + 1,
                "target_item_id": str(iid),
                "domain": str(dom),
                "main_category": str(mcat),
                "natural_query": q_natural,
                "hard_query": q_hard,
            })
    conn.close()
    return queries


def _eval_rank_list(candidates: list[str], target: str, ks=(10, 50, 100)) -> dict[str, float]:
    out: dict[str, float] = {}
    try:
        pos = candidates.index(target) + 1
    except ValueError:
        pos = None
    for k in ks:
        hit = 1.0 if (pos is not None and pos <= k) else 0.0
        mrr = (1.0 / pos) if (pos is not None and pos <= k) else 0.0
        ndcg = (1.0 / np.log2(pos + 1)) if (pos is not None and pos <= k) else 0.0
        out[f"recall@{k}"] = hit
        out[f"mrr@{k}"] = mrr
        out[f"ndcg@{k}"] = ndcg
    return out


def _paired_bootstrap(left: np.ndarray, right: np.ndarray, seed: int = 42, samples: int = 2000) -> dict:
    delta = left - right
    rng = np.random.default_rng(seed)
    means = [float(delta[rng.integers(len(delta), size=len(delta))].mean()) for _ in range(samples)]
    return {"mean_delta": float(delta.mean()), "ci95": np.percentile(means, [2.5, 97.5]).tolist()}


def main() -> None:
    ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--embeddings-path", type=Path, required=True)
    ap.add_argument("--bm25-index-path", type=Path, required=True)
    ap.add_argument("--ann-index-path", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--num-queries", type=int, default=250)
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    t0 = time.perf_counter()
    paths = resolve_bundle_paths(tag=args.tag)
    train, val, test = load_splits(paths.splits_dir, ("user_idx", "item_idx", "timestamp"))
    _, target_df = select_fit_target(train, val, test, "validation")
    _, item2id = load_mappings(paths.mapped_dir)
    id2item = {v: k for k, v in item2id.items()}
    cutoff = int(target_df.timestamp.min())

    val_items = sorted({id2item[int(i)] for i in target_df["item_idx"].unique() if int(i) in id2item})
    queries = _build_natural_queries(
        paths.corpus_path, val_items, cutoff=cutoff, num_queries=args.num_queries, seed=args.seed
    )
    print(f"[track-b] generated {len(queries)} English cold-start queries from eligible validation items", flush=True)

    store, encoder_impl, emb_prov = load_validated_embeddings(args.embeddings_path, paths.corpus_path)
    encoder = TextEncoder(encoder_impl.encode, dimension=store.dimension)
    bm25 = SparseBM25Index.load(args.bm25_index_path)
    ann_search = build_ann_search(store, {
        "index": "hnsw_sq8", "m": 32, "ef_search": 1024, "warmup_queries": 300, "warmup_limit": args.limit,
        "index_path": str(args.ann_index_path),
        "expected_embedding_build_id": emb_prov.get("build_id"),
    })

    # Build exact historical_static_catalog eligibility mask (first_seen_ts <= cutoff)
    conn = sqlite3.connect(f"file:{paths.corpus_path.resolve()}?mode=ro", uri=True)
    eligible_ids = {
        str(r[0]) for r in conn.execute(
            "SELECT item_id FROM items WHERE first_seen_ts IS NOT NULL AND first_seen_ts <= ?", (cutoff,)
        )
    }
    conn.close()
    bm25_valid = bm25.eligible_mask(eligible_ids)
    ann_valid = np.fromiter((i in eligible_ids for i in store.item_ids), dtype=bool, count=len(store.item_ids))
    print(f"[track-b] ready ({len(eligible_ids):,} eligible items) in {time.perf_counter()-t0:.1f}s", flush=True)

    report = {"tag": args.tag, "num_queries": len(queries), "limit": args.limit, "seed": args.seed, "regimes": {}}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "queries.jsonl").write_text(
        "\n".join(json.dumps(q, ensure_ascii=False) for q in queries) + "\n", encoding="utf-8"
    )

    for regime, field in (("natural_query", "natural_query"), ("hard_vocabulary_mismatch", "hard_query")):
        per_src = {s: [] for s in ("bm25", "dense", "hybrid")}
        lat = {s: [] for s in ("bm25", "dense", "hybrid")}
        for q in queries:
            text = q[field]
            target = q["target_item_id"]

            t_b = time.perf_counter()
            bm25_ids = bm25.search(text, valid_mask=bm25_valid, seen=None, limit=args.limit)
            lat["bm25"].append(time.perf_counter() - t_b)

            t_d = time.perf_counter()
            vec = np.asarray(encoder.encode([text])[0], dtype=np.float32)
            vec /= max(float(np.linalg.norm(vec)), 1e-12)
            dense_ids = ann_search(vec, ann_valid, set(), args.limit)
            lat["dense"].append(time.perf_counter() - t_d)

            t_h = time.perf_counter()
            hybrid_ids = [
                r["item_id"] for r in fuse_candidates({"bm25": bm25_ids, "dense": dense_ids}, budget=args.limit, rrf_k=60)
            ]
            lat["hybrid"].append(lat["bm25"][-1] + lat["dense"][-1] + (time.perf_counter() - t_h))

            per_src["bm25"].append(_eval_rank_list(bm25_ids, target))
            per_src["dense"].append(_eval_rank_list(dense_ids, target))
            per_src["hybrid"].append(_eval_rank_list(hybrid_ids, target))

        summary = {}
        for s in ("bm25", "dense", "hybrid"):
            keys = list(per_src[s][0].keys())
            summary[s] = {
                **{k: float(np.mean([r[k] for r in per_src[s]])) for k in keys},
                "p50_seconds": float(np.percentile(lat[s], 50)),
                "p95_seconds": float(np.percentile(lat[s], 95)),
            }
        deltas = {}
        for k in ("recall@10", "recall@100", "mrr@10", "ndcg@10"):
            bm = np.array([r[k] for r in per_src["bm25"]])
            dn = np.array([r[k] for r in per_src["dense"]])
            hy = np.array([r[k] for r in per_src["hybrid"]])
            deltas[f"dense_vs_bm25/{k}"] = _paired_bootstrap(dn, bm, seed=args.seed)
            deltas[f"hybrid_vs_bm25/{k}"] = _paired_bootstrap(hy, bm, seed=args.seed)
        report["regimes"][regime] = {"summary": summary, "paired_deltas": deltas}
        print(f"\n=== Track B ({regime}, n={len(queries)}) ===", flush=True)
        for s in ("bm25", "dense", "hybrid"):
            m = summary[s]
            print(f"  {s:8s}: R@10={m['recall@10']:.4f} R@50={m['recall@50']:.4f} R@100={m['recall@100']:.4f} "
                  f"MRR@10={m['mrr@10']:.4f} NDCG@10={m['ndcg@10']:.4f} | p95={m['p95_seconds']*1000:.1f}ms", flush=True)
        print("  hybrid vs bm25 R@100:", deltas["hybrid_vs_bm25/recall@100"], flush=True)
        print("  hybrid vs bm25 NDCG@10:", deltas["hybrid_vs_bm25/ndcg@10"], flush=True)

    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n[track-b] report saved -> {args.output / 'report.json'}", flush=True)


if __name__ == "__main__":
    main()
