"""Measure FilterTool-style recall with PER-TARGET single-category filters.

The first version pooled ALL of a user's target categories into one bucket —
realistic planners don't do that; they filter by ONE specific category per
intent. This version measures, for each held-out target independently: the
best popularity rank across each of the target's OWN category strings
(leaf categories + main_category), i.e. "planner issues FilterTool
categories=[<one correct category>]" — the true FilterTool ceiling.

Implementation: bulk-load rating_number for all items + cat->items once,
precompute top-1000-by-popularity rank map per category, then look up each
target's best rank. Identical semantics to FilterTool (EXISTS category match,
ORDER BY rating_number DESC) without the 5s query budget.

Usage (from src/):
    python scripts/evaluation/category_sql_recall.py <exp_dir>
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
import yaml

from package.config import load_config, get_domains
from package.config.resolve_bundle_paths import resolve_bundle_paths
from package.corpus import load_corpus
from package.corpus.apply_metadata_policy import apply_metadata_policy
from package.data.mapping import load_mappings
from package.data.split import load_splits
from package.evaluation.recommender.config import select_fit_target

RECALL_KS = (50, 200, 500, 1000)
TOP_N = 1000


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("exp_dir", type=Path)
    args = ap.parse_args()

    cfg = yaml.safe_load((args.exp_dir / "config.yaml").read_text(encoding="utf-8"))
    sampled = cfg["config"]["sampled_user_ids"]

    data_paths = resolve_bundle_paths()
    train, val, test = load_splits(data_paths.splits_dir, ("user_idx", "item_idx", "timestamp"))
    fit_df, target_df = select_fit_target(train, val, test, "validation")
    user2id, item2id = load_mappings(data_paths.mapped_dir)
    id2item = {v: k for k, v in item2id.items()}
    target_by_user = target_df.groupby("user_idx")["item_idx"].apply(set).to_dict()
    print("splits+mappings loaded", flush=True)

    eval_cfg = load_config("eval/candidate_recall")["candidate_recall"]
    meta_files = [(d, str(data_paths.meta_path(d))) for d in get_domains()]
    corpus, coverage = load_corpus(
        data_paths.corpus_path, meta_files, item2id,
        float(eval_cfg["min_metadata_coverage"]),
        allow_missing_sources=bool(eval_cfg.get("allow_missing_corpus_sources")))
    apply_metadata_policy(corpus, str(eval_cfg["metadata_policy"]),
                          as_of_timestamp=int(target_df.timestamp.min()))
    print(f"corpus loaded coverage={coverage:.3f}", flush=True)

    conn = corpus._conn  # read-only; bulk loads bypass the 5s progress-handler budget

    # rating_number for every visible item (NULL -> -inf, matching ORDER BY ... IS NULL first)
    rating: dict[str, float] = {}
    for iid, rn in conn.execute("SELECT item_id, rating_number FROM items").fetchall():
        rating[iid] = rn if rn is not None else -1.0
    print(f"ratings: {len(rating):,} items", flush=True)

    # category -> member item_ids, then top-TOP_N by rating per category
    cat_members: dict[str, list[str]] = {}
    for iid, cat in conn.execute("SELECT item_id, category FROM item_categories").fetchall():
        cat_members.setdefault(cat, []).append(iid)
    # main_category acts as a category string too (FilterTool validates against catalog;
    # main_category values also appear as item_categories rows, but include for completeness)
    cat_rank: dict[str, dict[str, int]] = {}
    for cat, members in cat_members.items():
        members.sort(key=lambda i: -rating.get(i, -1.0))
        cat_rank[cat] = {iid: r + 1 for r, iid in enumerate(members[:TOP_N])}
    print(f"cat_rank: {len(cat_rank)} cats", flush=True)

    # per-target categories (leaf + main_category)
    target_cats: dict[str, set[str]] = {}
    target_ids = []
    for seg, ulist in sampled.items():
        for u in ulist:
            for i in target_by_user.get(u, ()):
                if i in id2item:
                    target_ids.append((u, seg, i, id2item[i]))
    tids = [t[3] for t in target_ids]
    for cat, iid in conn.execute(
            "SELECT category, item_id FROM item_categories WHERE item_id IN ("
            + ",".join("?" for _ in tids) + ")", tids).fetchall():
        target_cats.setdefault(iid, set()).add(cat)
    for iid, mc in conn.execute(
            "SELECT item_id, main_category FROM items WHERE item_id IN ("
            + ",".join("?" for _ in tids) + ")", tids).fetchall():
        if mc:
            target_cats.setdefault(iid, set()).add(mc)
    print(f"targets: {len(target_ids)}, with_cats={len(target_cats)}", flush=True)

    per_target = []
    for u, seg, i, ns in target_ids:
        cats = target_cats.get(ns, set())
        best_rank = None
        best_cat = None
        for c in cats:
            r = cat_rank.get(c, {}).get(ns)
            if r is not None and (best_rank is None or r < best_rank):
                best_rank, best_cat = r, c
        per_target.append({
            "user_idx": u, "seg": seg, "item_idx": i, "item_id": ns,
            "n_cats": len(cats), "best_cat": best_cat, "sql_rank": best_rank,
        })

    n = len(per_target)
    report = {"exp_dir": str(args.exp_dir), "n_targets": n,
              "filtertool_single_category_popularity": {}}
    for k in RECALL_KS:
        hit = sum(1 for t in per_target if t["sql_rank"] is not None and t["sql_rank"] <= k)
        report["filtertool_single_category_popularity"][f"recall@{k}"] = round(hit / n, 4) if n else None
    in_top = sum(1 for t in per_target if t["sql_rank"] is not None)
    report["in_top1000_frac"] = round(in_top / n, 4) if n else None
    report["mean_cats_per_target"] = float(np.mean([t["n_cats"] for t in per_target])) if per_target else None
    buckets = Counter()
    for t in per_target:
        r = t["sql_rank"]
        if r is None:
            buckets["absent_or_deep"] += 1
        elif r <= 50:
            buckets["<=50"] += 1
        elif r <= 200:
            buckets["51-200"] += 1
        elif r <= 500:
            buckets["201-500"] += 1
        else:
            buckets["501-1000"] += 1
    report["rank_buckets"] = dict(buckets)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    out = args.exp_dir / "category_sql_recall.json"
    out.write_text(json.dumps({"report": report, "targets": per_target}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
