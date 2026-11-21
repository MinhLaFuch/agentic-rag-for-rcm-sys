"""A1 falsifier for the Q18 fix: does TRAIN INTERACTION COUNT order items as
well as rating_number for FilterTool candidate recall?

Same harness/sample as q4_filter_orderings.py (exp_003 oracle sample, 155
targets, per-target best-category rank, visible items only, as_of from
target_df). Adds ordering keys:

  train_count_desc : COUNT of train.parquet interactions per item
                     (CAUSAL — pre-cutoff_1 by construction; the proposed
                     replacement for masked rating_number)
  rating_number_desc : reference (best measured, but leaks future in eval)
  item_id_asc       : control = what eval actually produces under masking

If train_count r@200 approaches rating_number's ~38.7%, the Q18 fix
(causal popularity ordering) is justified. If it collapses toward item_id's
~0.65%, report-only.

Output: investigations/q4b_traincount_ordering.json
"""
from __future__ import annotations

import json
import sqlite3
import sys
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
SPLITS = Path("resource/splits/multi_domain")
RECALL_KS = (50, 200, 500, 1000)
TOP_N = 1000
OUT = Path(__file__).parent / "q4b_traincount_ordering.json"

ORDERINGS = {
    "train_count_desc": "train_count",
    "rating_number_desc": "rating_number",
    "item_id_asc": "item_id",
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

    # ---- train interaction count per item (item_idx space) ----
    tc = train["item_idx"].value_counts()
    train_count_by_name = {id2item[i]: int(c) for i, c in tc.items() if i in id2item}
    del train, tc
    print(f"train_count map: {len(train_count_by_name):,} items", flush=True)

    conn = sqlite3.connect(
        "file:resource/corpus/multi_domain/corpus_multi_domain.sqlite?mode=ro",
        uri=True)
    as_of = int(target_df.timestamp.min())
    attrs = {}
    for iid, rn, fs in conn.execute(
            "SELECT item_id, rating_number, first_seen_ts FROM main.items").fetchall():
        attrs[iid] = {"rating_number": rn, "first_seen_ts": fs,
                      "train_count": train_count_by_name.get(iid, 0)}
    print(f"attrs: {len(attrs):,}", flush=True)

    visible = {r[0] for r in conn.execute(
        "SELECT item_id FROM items WHERE first_seen_ts IS NOT NULL AND first_seen_ts <= ?",
        (as_of,))}
    print(f"visible: {len(visible):,}", flush=True)

    cat_members: dict[str, list[str]] = {}
    for iid, cat in conn.execute("SELECT item_id, category FROM item_categories").fetchall():
        if iid in visible:
            cat_members.setdefault(cat, []).append(iid)
    print(f"cats: {len(cat_members)}", flush=True)

    rank_maps = {}
    for oname, key in ORDERINGS.items():
        rm = {}
        for cat, members in cat_members.items():
            if key == "item_id":
                members.sort()
            elif key == "train_count":
                members.sort(key=lambda i: (-attrs.get(i, {}).get("train_count", 0), i))
            else:  # rating_number DESC, NULLs last, item_id tiebreak
                def k(i, a=attrs):
                    v = a.get(i, {}).get("rating_number")
                    try:
                        fv = float(v)
                    except (TypeError, ValueError):
                        fv = None
                    return (0, -fv, i) if fv is not None else (1, 0.0, i)
                members.sort(key=k)
            rm[cat] = {iid: r + 1 for r, iid in enumerate(members[:TOP_N])}
        rank_maps[oname] = rm
        print(f"ordering {oname} done", flush=True)

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

    # ordering-agreement diagnostic: Spearman between train_count and
    # rating_number ranks over visible catalog (sample 200k for speed)
    sample_ids = list(visible)[::max(1, len(visible) // 200000)]
    tc_arr = np.array([attrs[i]["train_count"] for i in sample_ids], dtype=float)
    rn_arr = np.array([float(attrs[i]["rating_number"] or 0) for i in sample_ids])
    spear = float(pd.Series(tc_arr).corr(pd.Series(rn_arr), method="spearman"))

    report = {"exp_dir": str(EXP_DIR), "n_targets": len(target_ids),
              "note": "train_count = causal train.parquet interaction count; "
                      "proposed Q18 replacement ordering under historical policy",
              "spearman_train_count_vs_rating_number_sample": spear,
              "orderings": {}}
    for oname in ORDERINGS:
        rm = rank_maps[oname]
        ranks = []
        for u, seg, i, ns in target_ids:
            best = None
            for c in target_cats.get(ns, set()):
                r = rm.get(c, {}).get(ns)
                if r is not None and (best is None or r < best):
                    best = r
            ranks.append(best)
        rec = {f"recall@{k}": round(sum(1 for r in ranks if r is not None and r <= k) / len(ranks), 4)
               for k in RECALL_KS}
        rec["in_top1000_frac"] = round(sum(1 for r in ranks if r is not None) / len(ranks), 4)
        rec["median_rank"] = float(np.median([r for r in ranks if r is not None])) \
            if any(r is not None for r in ranks) else None
        report["orderings"][oname] = rec
        print(oname, rec, flush=True)

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
