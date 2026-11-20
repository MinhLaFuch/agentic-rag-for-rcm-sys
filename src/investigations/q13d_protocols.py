"""Q13 recheck part 3: visibility-protocol comparison (offline measurement only).

The eval rewinds to cutoff_1 and hides items whose first_seen_ts > as_of —
a proxy for "item didn't exist yet". User's question: do we need this proxy
at all, and what do alternative protocols cost/benefit?

Protocols (same 196 campaign_005 exp_5 targets, same timestamps):
  A  current:      single as_of=1617737606549 + first_seen filter
  B  per-target:   as_of_t = target_ts - 1ms (target visible by construction,
                   except items whose FIRST-EVER interaction is the target)
  C  late cutoff:  as_of = max interaction timestamp in data (end of test),
                   first_seen filter still applied -> ~nothing hidden
  D  no filter:    entire catalog visible (incl. items with no interactions)

Per protocol report: n_targets, hidden count/rate, and candidate-recall
ceiling = fraction of ALL 196 targets whose best-category rank under
rating_number DESC ordering is <= K (K=200,1000) among that protocol's
visible competitor set. Same ordering semantics as FilterTool/Q4
(rating_number DESC, NULLs last, item_id tiebreak — approximated by global
item order; rating_number has 0 NULLs so only value-ties are affected).

Future-information note: meta rating_number/price/average_rating are
scrape-time snapshots -> they contain post-cutoff information under EVERY
protocol A-C (and trivially under D). Only train-derived signals are causal.

Output: investigations/q13d_protocols.json
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
DB = "resource/corpus/multi_domain/corpus_multi_domain.sqlite"
SPLITS = Path("resource/splits/multi_domain")
AS_OF_A = 1617737606549
KS = (200, 1000)
OUT = Path(__file__).parent / "q13d_protocols.json"


def main() -> None:
    targets = pd.read_parquet(Path(__file__).parent / "q13c_targets.parquet")
    print(f"targets: {len(targets)}", flush=True)

    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

    # ---- items: ordering key (rating_number) + first_seen ----
    items = pd.DataFrame(conn.execute(
        "SELECT item_id, rating_number, first_seen_ts FROM main.items"
    ).fetchall(), columns=["item_id", "rn", "fs"])
    items["rn_f"] = pd.to_numeric(items["rn"], errors="coerce")
    N = len(items)
    # FilterTool order: rating_number DESC, NULLs last, item_id ASC
    items = items.sort_values(["rn_f", "item_id"],
                              ascending=[False, True],
                              na_position="last", kind="mergesort")
    items["ord"] = np.arange(N, dtype=np.int64)
    code_of = {iid: c for c, iid in enumerate(items.item_id)}
    ord_of_code = items["ord"].to_numpy()
    fs_of_code = items["fs"].to_numpy(dtype=np.float64)  # NaN if NULL
    print(f"items: {N:,}", flush=True)

    # ---- item_categories -> global (cat_code, ord, fs) sorted once ----
    ic = pd.read_sql_query("SELECT item_id, category FROM item_categories", conn)
    ic["code"] = ic.item_id.map(code_of)
    ic = ic[ic.code.notna()]
    ic["code"] = ic.code.astype(np.int64)
    ic["cat_code"], cat_uniques = pd.factorize(ic.category)
    ic["ord"] = ord_of_code[ic.code.to_numpy()]
    ic["fs"] = fs_of_code[ic.code.to_numpy()]
    print(f"item_categories rows: {len(ic):,}, cats: {len(cat_uniques)}", flush=True)

    ic = ic.sort_values(["cat_code", "ord"], kind="mergesort")
    cat_sorted = ic.cat_code.to_numpy()
    ord_sorted = ic.ord.to_numpy()
    fs_sorted = ic.fs.to_numpy()
    change = np.flatnonzero(np.diff(cat_sorted)) + 1
    starts = np.concatenate([[0], change])
    cat_slices = {}
    cat_names = cat_uniques.tolist()
    for s, cc in zip(starts, cat_sorted[starts]):
        cat_slices[cat_names[int(cc)]] = (int(s), int(s + np.searchsorted(
            cat_sorted[s:], cc, side="right") - np.searchsorted(cat_sorted[s:], cc)))
    # simpler: ends via next start
    ends = np.concatenate([change, [len(cat_sorted)]])
    cat_slices = {cat_names[int(cc)]: (int(s), int(e))
                  for s, e, cc in zip(starts, ends, cat_sorted[starts])}
    print("cat slices built", flush=True)

    # ---- main_category pseudo-categories for target cats not in item_categories ----
    target_ids = targets.item_id.unique().tolist()
    tids = ",".join("?" for _ in target_ids)
    tcat_rows = conn.execute(
        f"SELECT item_id, category FROM item_categories WHERE item_id IN ({tids})",
        target_ids).fetchall()
    tmc_rows = conn.execute(
        f"SELECT item_id, main_category FROM main.items WHERE item_id IN ({tids}) "
        "AND main_category IS NOT NULL AND main_category != ''",
        target_ids).fetchall()
    tcats = {}
    for iid, c in tcat_rows:
        tcats.setdefault(iid, set()).add(c)
    for iid, c in tmc_rows:
        tcats.setdefault(iid, set()).add(c)
    targets["cats"] = targets.item_id.map(lambda x: sorted(tcats.get(x, ())))
    print(f"targets with >=1 cat: {int((targets.cats.map(len) > 0).sum())}/{len(targets)}",
          flush=True)

    # main_category members for needed pseudo-cats only
    needed_mc = {c for cats in tcats.values() for c in cats}
    # which of those are NOT real item_categories names?
    real_cat_names = set(cat_slices.keys())
    pseudo = needed_mc - real_cat_names
    mc_slices = {}
    if pseudo:
        ph = ",".join("?" for _ in pseudo)
        sub = pd.DataFrame(conn.execute(
            f"SELECT item_id, main_category FROM main.items "
            f"WHERE main_category IN ({ph})", list(pseudo)).fetchall(),
            columns=["item_id", "main_category"])
        sub["code"] = sub.item_id.map(code_of)
        sub = sub[sub.code.notna()]
        sub["code"] = sub.code.astype(np.int64)
        sub["ord"] = ord_of_code[sub.code.to_numpy()]
        sub["fs"] = fs_of_code[sub.code.to_numpy()]
        sub = sub.sort_values(["main_category", "ord"], kind="mergesort")
        mc_cat = sub.main_category.to_numpy()
        mc_ord = sub.ord.to_numpy()
        mc_fs = sub.fs.to_numpy()
        ch = np.flatnonzero(mc_cat[1:] != mc_cat[:-1]) + 1
        mstarts = np.concatenate([[0], ch]); mends = np.concatenate([ch, [len(mc_cat)]])
        for s, e, cc in zip(mstarts, mends, mc_cat[mstarts]):
            mc_slices[str(cc)] = (mc_ord[s:e], mc_fs[s:e])
    print(f"pseudo main_category slices: {len(mc_slices)}", flush=True)

    # per-target lookups
    ord_map = dict(zip(items.item_id, items.ord))
    fs_map = dict(zip(items.item_id, items.fs))
    targets["ord"] = targets.item_id.map(ord_map)
    targets["fs"] = targets.item_id.map(fs_map)

    test_max = int(pd.read_parquet(SPLITS / "test.parquet", columns=["timestamp"])
                   ["timestamp"].max())
    print(f"data end (test max ts): {test_max}", flush=True)

    def best_rank(cats, ord_t, as_of, include_null_fs):
        best = None
        for c in cats:
            if c in cat_slices:
                s, e = cat_slices[c]
                ords = ord_sorted[s:e]; fss = fs_sorted[s:e]
            elif c in mc_slices:
                ords, fss = mc_slices[c]
            else:
                continue
            pos = int(np.searchsorted(ords, ord_t))
            if pos >= len(ords) or ords[pos] != ord_t:
                continue
            if include_null_fs:
                vis = pos
            else:
                vis = int(((fss[:pos] <= as_of) & ~np.isnan(fss[:pos])).sum())
            rk = vis + 1
            if best is None or rk < best:
                best = rk
        return best

    protocols = {
        "A_current_single_cutoff": {
            "hidden": lambda r: bool(pd.isna(r["fs"]) or r["fs"] > AS_OF_A),
            "as_of": lambda r: AS_OF_A, "include_null_fs": False},
        "B_per_target_rewind": {
            "hidden": lambda r: bool(pd.isna(r["fs"]) or r["fs"] >= r["target_ts"]),
            "as_of": lambda r: r["target_ts"] - 1, "include_null_fs": False},
        "C_late_cutoff_end_of_data": {
            "hidden": lambda r: bool(pd.isna(r["fs"]) or r["fs"] > test_max),
            "as_of": lambda r: float(test_max), "include_null_fs": False},
        "D_no_visibility_filter": {
            "hidden": lambda r: False,
            "as_of": lambda r: np.inf, "include_null_fs": True},
    }

    report = {"method": "per-target best-category rank under rating_number DESC "
              "(FilterTool order) among protocol-visible competitors; ceiling = "
              "share of all 196 targets with rank<=K; hidden or no-category "
              "targets count as misses",
              "n_targets": int(len(targets)), "ks": list(KS),
              "ordering": "rating_number DESC, NULLs last, item_id tiebreak "
                          "(tiebreak approximated by global item order)",
              "future_info_note": "meta rating_number/price/average_rating are "
                  "scrape-time snapshots -> contain post-cutoff information under "
                  "protocols A/B/C (and trivially D). Only train-derived counts "
                  "are causal. rating_number vs held-out interactions "
                  "Spearman=0.65 quantifies the leaked future signal.",
              "protocols": {}}

    trows = targets.to_dict("records")
    for pname, p in protocols.items():
        n_hidden = 0
        n_unranked = 0
        hits = {k: 0 for k in KS}
        best_ranks = []
        for r in trows:
            if p["hidden"](r):
                n_hidden += 1
                best_ranks.append(None)
                continue
            rk = best_rank(r["cats"], r["ord"], p["as_of"](r),
                           p["include_null_fs"]) if r["cats"] else None
            if rk is None:
                n_unranked += 1
            best_ranks.append(rk)
            for k in KS:
                if rk is not None and rk <= k:
                    hits[k] += 1
        entry = {"n_hidden": int(n_hidden),
                 "hidden_pct": round(100 * n_hidden / len(trows), 2),
                 "n_visible_but_unranked_no_cat_or_not_member": int(n_unranked),
                 "recall": {f"@{k}": round(hits[k] / len(trows), 4) for k in KS},
                 "median_best_rank_visible": (
                     float(np.median([x for x in best_ranks if x is not None]))
                     if any(x is not None for x in best_ranks) else None)}
        report["protocols"][pname] = entry
        print(pname, entry, flush=True)

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str),
                   encoding="utf-8")
    print("wrote", OUT, flush=True)


if __name__ == "__main__":
    main()
