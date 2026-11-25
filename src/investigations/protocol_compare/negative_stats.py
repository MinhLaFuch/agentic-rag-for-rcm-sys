"""Negative-difficulty stats for the protocol emulation: for each negative
variant, measure how 'hard' the sampled negatives are relative to the target.

  - category_overlap : fraction of negatives sharing the target's deepest
                       category (item_categories, last browse-path node)
  - popularity_gap   : median global popularity rank of negatives minus
                       median rank of the target (rank 0 = most popular).
                       Negative => negatives MORE popular than target
                       (harder for a popularity baseline); positive =>
                       target more popular than its negatives (easier).

Same data anchors as protocol_emulation.py. Writes negative_stats.json.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "negative_stats.json"

REQS = ROOT / "experiments/agent_eval/campaigns/campaign_005" \
    / "exp_5_agents_planner_inference_mode_template_reflect_rounds_0_multi_turn_True" \
    / "run_1/requests.jsonl"
ITEM2ID = ROOT / "resource/mapped/multi_domain/item2id.json"
TRAIN = ROOT / "resource/splits/multi_domain/train.parquet"
DB = ROOT / "resource/corpus/multi_domain/corpus_multi_domain.sqlite"
AS_OF = 1617737606549
SEEDS = list(range(5))


def main() -> None:
    item2id = json.loads(ITEM2ID.read_text(encoding="utf-8"))
    idx2name = {v: k for k, v in item2id.items()}
    name2idx = item2id
    num_items = len(item2id)

    cases = []
    for l in open(REQS, encoding="utf-8"):
        r = json.loads(l)
        for t in r.get("targets", []):
            if t in idx2name:
                cases.append(t)

    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    vis_names = [r[0] for r in conn.execute(
        "SELECT item_id FROM items WHERE first_seen_ts <= ?", (AS_OF,))]
    cat_map: dict[str, str] = {}
    cur_item, cur_cat = None, None
    for iid, cat in conn.execute(
            "SELECT item_id, category FROM item_categories ORDER BY item_id, rowid"):
        if iid != cur_item:
            cur_item, cur_cat = iid, cat
        else:
            cur_cat = cat
        cat_map[cur_item] = cur_cat
    conn.close()

    univ_idx = np.array([name2idx[n] for n in vis_names if n in name2idx],
                        dtype=np.int64)
    N = len(univ_idx)

    fit = pd.read_parquet(TRAIN, columns=["item_idx"])
    pop = np.zeros(num_items, dtype=np.int64)
    vc = fit["item_idx"].value_counts()
    pop[vc.index.to_numpy()] = vc.to_numpy()

    # global popularity rank over universe (pop desc, idx asc)
    order = np.lexsort((univ_idx, -pop[univ_idx]))
    rank_of = np.empty(num_items, dtype=np.int64)
    rank_of[univ_idx[order]] = np.arange(N)
    univ_set = set(int(x) for x in univ_idx)

    def cat_of(i: int):
        return cat_map.get(idx2name.get(int(i), ""))

    # category code per universe item (-1 = none)
    cat_code: dict[str, int] = {}
    univ_cat = np.empty(N, dtype=np.int64)
    for p, i in enumerate(univ_idx):
        c = cat_map.get(idx2name[int(i)])
        if c is None:
            univ_cat[p] = -1
        else:
            if c not in cat_code:
                cat_code[c] = len(cat_code)
            univ_cat[p] = cat_code[c]

    # category membership masks only for cats that appear as targets
    target_cats = {cat_code.get(cat_of(t), -1) for t in cases}
    target_cats.discard(-1)
    member_mask = {code: (univ_cat == code) for code in target_cats}

    w = pop[univ_idx].astype(np.float64)
    pop_cdf = np.cumsum(w) / w.sum()

    rng = np.random.default_rng(777)
    stats = {v: {"cat_overlap": [], "pop_gap": []} for v in
             ("uniform", "popneg", "catneg")}
    POPN, CATN = 100, 100  # measure at pool-100 scale (superset of pool-10)

    def sample_uniform(exclude: set[int], n: int) -> np.ndarray:
        res, seen = [], set(exclude)
        while len(res) < n:
            pos = rng.integers(0, N, size=(n - len(res)) * 2)
            for it in univ_idx[pos]:
                i = int(it)
                if i not in seen:
                    seen.add(i)
                    res.append(i)
                    if len(res) == n:
                        return np.array(res, dtype=np.int64)
        return np.array(res, dtype=np.int64)

    for t in cases:
        tcat = cat_of(t)
        t_rank = int(rank_of[t]) if int(t) in univ_set else N
        for variant in stats:
            overlaps, gaps = [], []
            for _ in SEEDS:
                if variant == "uniform":
                    neg = sample_uniform({int(t)}, POPN)
                elif variant == "popneg":
                    res, seen = [], {int(t)}
                    while len(res) < POPN:
                        u = rng.random((POPN - len(res)) * 3)
                        pos = np.clip(np.searchsorted(pop_cdf, u), 0, N - 1)
                        for i in univ_idx[pos]:
                            i = int(i)
                            if pop[i] > 0 and i not in seen:
                                seen.add(i)
                                res.append(i)
                                if len(res) == POPN:
                                    break
                    neg = np.array(res, dtype=np.int64)
                else:  # catneg
                    tcode = cat_code.get(tcat, -1)
                    mem = univ_idx[member_mask[tcode]] \
                        if tcode in member_mask else np.empty(0, dtype=np.int64)
                    mem = mem[mem != t]
                    take = min(CATN, len(mem))
                    out = [int(x) for x in rng.choice(mem, size=take, replace=False)] \
                        if take else []
                    if take < CATN:
                        out.extend(sample_uniform(set(out) | {int(t)}, CATN - take).tolist())
                    neg = np.array(out[:CATN], dtype=np.int64)
                if tcat is not None:
                    overlaps.append(float(np.mean([cat_of(int(i)) == tcat
                                                   for i in neg])))
                else:
                    overlaps.append(np.nan)
                neg_ranks = np.array([int(rank_of[i]) for i in neg])
                gaps.append(float(np.median(neg_ranks) - t_rank))
            stats[variant]["cat_overlap"].append(float(np.nanmean(overlaps)))
            stats[variant]["pop_gap"].append(float(np.mean(gaps)))

    report = {"note": "pop_gap = median rank(negatives) - rank(target), "
                      "rank 0 = most popular; negative => negatives more "
                      "popular than target (harder pool)",
              "n_cases": len(cases), "pool_n": POPN, "seeds": SEEDS,
              "per_variant": {}}
    for v, d in stats.items():
        co = np.array(d["cat_overlap"], dtype=float)
        pg = np.array(d["pop_gap"], dtype=float)
        report["per_variant"][v] = {
            "category_overlap_mean": float(np.nanmean(co)),
            "category_overlap_median": float(np.nanmedian(co)),
            "popularity_gap_mean": float(pg.mean()),
            "popularity_gap_median": float(np.median(pg)),
            "popularity_gap_std": float(pg.std()),
        }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(json.dumps(report["per_variant"], indent=2))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
