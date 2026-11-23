"""Q4: FilterTool candidate-ordering variants — which slice ordering recalls targets best?

Same target set/method as scripts/evaluation/category_sql_recall.py (exp_003
oracle sample, per-target best single-category rank), but computes the best
rank under SEVERAL ORDER BY keys instead of only rating_number:

  rating_number DESC  (popularity / review count — NOTE: masked=NULL in eval)
  average_rating DESC (quality)
  first_seen_ts DESC  (recency proxy — newest items first)
  price ASC           (cheap-first; NULLs last per FilterTool IS NULL semantics)
  item_id ASC         (what eval ACTUALLY produces under NULL masking — control)

For each ordering: per-category top-1000 rank map -> per-target best rank ->
recall@50/200/500/1000. Read-only bulk loads bypass the 5s SQL budget (same as
category_sql_recall). Outputs investigations/q4_filter_orderings.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from package.config.resolve_bundle_paths import resolve_bundle_paths
from package.data.mapping import load_mappings
from package.data.split import load_splits
from package.evaluation.recommender.config import select_fit_target

EXP_DIR = Path("experiments/candidate_recall/exp_003")
RECALL_KS = (50, 200, 500, 1000)
TOP_N = 1000
OUT = Path(__file__).parent / "q4_filter_orderings.json"

# ordering name -> (sql column, ascending?)  NULLs always sort last (FilterTool semantics)
ORDERINGS = {
    "rating_number_desc": ("rating_number", False),
    "average_rating_desc": ("average_rating", False),
    "first_seen_ts_desc": ("first_seen_ts", False),
    "price_asc": ("price", True),
    "item_id_asc": ("item_id", True),  # control: eval's effective order under masking
}


def main() -> None:
    cfg = yaml.safe_load((EXP_DIR / "config.yaml").read_text(encoding="utf-8"))
    sampled = cfg["config"]["sampled_user_ids"]

    data_paths = resolve_bundle_paths()
    train, val, test = load_splits(data_paths.splits_dir, ("user_idx", "item_idx", "timestamp"))
    fit_df, target_df = select_fit_target(train, val, test, "validation")
    user2id, item2id = load_mappings(data_paths.mapped_dir)
    id2item = {v: k for k, v in item2id.items()}
    target_by_user = target_df.groupby("user_idx")["item_idx"].apply(set).to_dict()
    print("splits+mappings loaded", flush=True)

    # raw read-only connection to the corpus file (no eval authorizer, no temp views)
    import sqlite3
    conn = sqlite3.connect(
        "file:resource/corpus/multi_domain/corpus_multi_domain.sqlite?mode=ro",
        uri=True)
    as_of = int(target_df.timestamp.min())
    print("raw connection ready", flush=True)

    # item attributes from the VISIBLE items view — note: rating_number etc are
    # masked to NULL under historical_static_catalog, so read MAIN table instead
    # for ordering keys (analysis measures "what ordering WOULD do", not eval's).
    attrs = {}
    for iid, rn, ar, fs, pr in conn.execute(
            "SELECT item_id, rating_number, average_rating, first_seen_ts, price FROM main.items").fetchall():
        attrs[iid] = (rn, ar, fs, pr)
    print(f"attrs: {len(attrs):,}", flush=True)

    # visible set under historical_static_catalog = first_seen_ts <= as_of
    visible = {r[0] for r in conn.execute(
        "SELECT item_id FROM items WHERE first_seen_ts IS NOT NULL AND first_seen_ts <= ?",
        (as_of,))}
    print(f"visible: {len(visible):,} (as_of={as_of})", flush=True)

    # category -> member visible item_ids
    cat_members: dict[str, list[str]] = {}
    for iid, cat in conn.execute("SELECT item_id, category FROM item_categories").fetchall():
        if iid in visible:
            cat_members.setdefault(cat, []).append(iid)
    print(f"cats: {len(cat_members)}", flush=True)

    # per-ordering rank maps: cat -> {item_id: rank<=TOP_N}
    col_idx = {"rating_number": 0, "average_rating": 1, "first_seen_ts": 2, "price": 3}
    rank_maps: dict[str, dict[str, dict[str, int]]] = {}
    for oname, (col, asc) in ORDERINGS.items():
        ci = col_idx.get(col)
        rm: dict[str, dict[str, int]] = {}
        for cat, members in cat_members.items():
            if col == "item_id":
                members.sort()
            else:
                # NULLs last; for DESC use -val, for ASC use +val with NULL->+inf
                def key(i, ci=ci, asc=asc):
                    v = attrs.get(i, (None,) * 4)[ci]
                    if v is None:
                        return (1, 0.0) if not asc else (1, 0.0)
                    return (0, v if asc else -v)
                members.sort(key=key)
            rm[cat] = {iid: r + 1 for r, iid in enumerate(members[:TOP_N])}
        rank_maps[oname] = rm
        print(f"  ordering {oname} done", flush=True)

    # targets (same as category_sql_recall)
    target_ids = []
    for seg, ulist in sampled.items():
        for u in ulist:
            for i in target_by_user.get(u, ()):
                if i in id2item:
                    target_ids.append((u, seg, i, id2item[i]))
    tids = [t[3] for t in target_ids]
    target_cats: dict[str, set[str]] = {}
    for cat, iid in conn.execute(
            "SELECT category, item_id FROM item_categories WHERE item_id IN ("
            + ",".join("?" for _ in tids) + ")", tids).fetchall():
        target_cats.setdefault(iid, set()).add(cat)
    for iid, mc in conn.execute(
            "SELECT item_id, main_category FROM main.items WHERE item_id IN ("
            + ",".join("?" for _ in tids) + ")", tids).fetchall():
        if mc:
            target_cats.setdefault(iid, set()).add(mc)
    print(f"targets: {len(target_ids)}, with_cats={len(target_cats)}", flush=True)

    report = {"exp_dir": str(EXP_DIR), "n_targets": len(target_ids),
              "note": "ranks computed on UNMASKED main.items ordering keys; eval's effective order under masking is item_id_asc (control row)",
              "orderings": {}}
    for oname in ORDERINGS:
        rm = rank_maps[oname]
        per_target_ranks = []
        for u, seg, i, ns in target_ids:
            best = None
            for c in target_cats.get(ns, set()):
                r = rm.get(c, {}).get(ns)
                if r is not None and (best is None or r < best):
                    best = r
            per_target_ranks.append(best)
        n = len(per_target_ranks)
        rec = {f"recall@{k}": round(sum(1 for r in per_target_ranks if r is not None and r <= k) / n, 4)
               for k in RECALL_KS}
        rec["in_top1000_frac"] = round(sum(1 for r in per_target_ranks if r is not None) / n, 4)
        rec["median_rank"] = float(np.median([r for r in per_target_ranks if r is not None])) \
            if any(r is not None for r in per_target_ranks) else None
        report["orderings"][oname] = rec
        print(oname, rec, flush=True)

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
