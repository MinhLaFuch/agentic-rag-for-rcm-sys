"""Phase 4b — spec ablation: gold vs predicted spec as filters on real trajectories.

For each of the 152 agent_eval requests we take the baseline exp_2 trajectory's
``recommended`` list and measure how well GOLD spec vs PREDICTED spec (extractor
output on the original text) constrains/ranks it:

- cold_text / similar: spec_sat@10 = fraction of top-10 whose coarse bucket
  equals the spec's resolved coarse bucket (strict: uncategorized fails).
- exclusion: spec_violation@10 = fraction of requests with >=1 excluded item
  or item carrying an excluded category label in top-10.
- personalized / ambiguous / unanswerable: no enforceable spec -> pass-through.

The delta gold-vs-predicted = the end-to-end cost of extractor error, i.e. the
headroom a perfect extractor would recover over the current one.

Usage: python investigations/spec_benchmark/ablate_specs.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

OUT = Path("investigations/spec_benchmark")
RUN = Path("experiments/agent_eval/filter_ab/exp_2_baseline/run_1")
CORPUS = "resource/corpus/multi_domain/corpus_multi_domain.sqlite"
VIEW = Path("investigations/distill_phase2/item_spec_view.parquet")
COARSE_MIN_ITEMS = 1000
CAT_KINDS = {"cold_text", "similar"}


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def label_counts(conn) -> dict[str, int]:
    cache = OUT / "label_counts.json"
    if cache.is_file():
        return json.loads(cache.read_text())
    counts = {r[0]: r[1] for r in conn.execute(
        "SELECT category, COUNT(*) FROM item_categories GROUP BY category")}
    cache.write_text(json.dumps(counts))
    return counts


def slot_value(spec: dict, name: str):
    s = (spec or {}).get(name)
    if isinstance(s, dict):
        return s.get("value")
    return s


def build_label_coarse(conn, view: dict, labels: set[str]) -> dict[str, str | None]:
    """label -> coarse bucket = majority coarse of items carrying that label
    (same leaf-up semantics as gold, which derives coarse from item sequences).
    The taxonomy is a DAG — ancestors/depth proxies are unreliable, so we
    resolve via item evidence instead."""
    cache = OUT / "label_coarse_map.json"
    saved = json.loads(cache.read_text()) if cache.is_file() else {}
    out = dict(saved)
    for lab in labels:
        if lab in out:
            continue
        iids = [r[0] for r in conn.execute(
            "SELECT item_id FROM item_categories WHERE category = ? LIMIT 20000", (lab,))]
        votes: dict[str, int] = defaultdict(int)
        for iid in iids:
            v = view.get(iid)
            if v and v["coarse"] and v["has_categories"]:
                votes[v["coarse"]] += 1
        out[lab] = max(votes, key=votes.get) if votes else None
    cache.write_text(json.dumps(out))
    return out


def predicted_coarse(pred: dict, kind: str, view: dict, l2c: dict) -> str | None:
    """Resolve a predicted spec to a coarse bucket.
    similar: gold coarse IS the seed's coarse -> prefer seed_item_id lookup.
    cold_text: category slots (leaf preferred) via label->coarse item evidence."""
    if kind == "similar":
        seed = pred.get("seed_item_id")
        if seed and seed in view and view[seed]["coarse"]:
            return view[seed]["coarse"]
    for slot in ("category_leaf", "category_coarse"):
        lab = slot_value(pred, slot)
        if isinstance(lab, str) and lab.strip():
            c = l2c.get(lab)
            if c:
                return c
    if kind == "similar":
        seed = pred.get("seed_item_id")
        if seed and seed in view:
            return view[seed]["coarse"]
    return None


def main() -> None:
    gold = {r["request_id"]: r for r in load_jsonl(OUT / "gold_specs.jsonl")}
    preds = {r["request_id"]: r for r in load_jsonl(OUT / "extractor_outputs.jsonl")
             if r["variant"] == "original"}
    trajs = {t["request_id"]: t for t in load_jsonl(RUN / "trajectories.jsonl")}

    conn = sqlite3.connect(f"file:{CORPUS}?mode=ro", uri=True)

    view_df = pd.read_parquet(VIEW).set_index("item_id")
    view = {}
    for iid, row in view_df.iterrows():
        coarse = row["coarse"]
        if coarse is None or coarse != coarse:  # NaN from pandas
            coarse = None
        view[iid] = {"coarse": coarse, "has_categories": bool(row["has_categories"])}
    del view_df

    # collect every predicted category label, resolve label->coarse once
    pred_labels: set[str] = set()
    for r in preds.values():
        spec = r.get("spec") or {}
        for slot in ("category_leaf", "category_coarse"):
            lab = slot_value(spec, slot)
            if isinstance(lab, str) and lab.strip():
                pred_labels.add(lab)
    l2c = build_label_coarse(conn, view, pred_labels)
    print(f"label->coarse resolved for {len(l2c)} labels "
          f"({sum(1 for v in l2c.values() if v)} hit)", flush=True)

    cat_cache: dict[str, frozenset[str]] = {}

    def item_cats(iid: str) -> frozenset[str]:
        if iid not in cat_cache:
            cat_cache[iid] = frozenset(
                r[0] for r in conn.execute(
                    "SELECT category FROM item_categories WHERE item_id = ?", (iid,)))
        return cat_cache[iid]

    rows = []
    for rid, g in gold.items():
        kind = g["kind"]
        traj = trajs.get(rid)
        rec = (traj or {}).get("recommended") or []
        top = rec[:10]
        pred = (preds.get(rid) or {}).get("spec") or {}
        gspec = g["spec"]

        row = {"request_id": rid, "kind": kind}
        if kind in CAT_KINDS:
            g_coarse = g.get("gold_coarse")
            if g_coarse is None or g_coarse != g_coarse:
                g_coarse = None
            p_coarse = predicted_coarse(pred, kind, view, l2c)
            if p_coarse is not None and p_coarse != p_coarse:
                p_coarse = None
            row.update({
                "gold_coarse": g_coarse, "pred_coarse": p_coarse,
                "coarse_agree": g_coarse == p_coarse,
            })
            for tag, coarse in (("gold", g_coarse), ("pred", p_coarse)):
                sat = [1 if (iid in view and view[iid]["coarse"] == coarse
                             and view[iid]["has_categories"]) else 0
                       for iid in top]
                row[f"{tag}_sat@10"] = sum(sat) / 10 if top else 0.0
                row[f"{tag}_coverage"] = float(len(top) > 0)
        elif kind == "exclusion":
            for tag, spec in (("gold", gspec), ("pred", pred)):
                ex = (spec or {}).get("exclusions") or {}
                ex_ids, ex_cats = set(ex.get("item_ids") or []), set(ex.get("category_labels") or [])
                viol = 0
                for iid in top:
                    if iid in ex_ids or (item_cats(iid) & ex_cats):
                        viol += 1
                row[f"{tag}_viol@10"] = viol / 10 if top else 0.0
                row[f"{tag}_any_viol"] = float(viol > 0)
                row[f"{tag}_coverage"] = float(len(top) > 0)
            # constraint presence agreement
            ge = set((gspec.get("exclusions") or {}).get("item_ids") or []) | \
                 set((gspec.get("exclusions") or {}).get("category_labels") or [])
            pe = set((pred.get("exclusions") or {}).get("item_ids") or []) | \
                 set((pred.get("exclusions") or {}).get("category_labels") or [])
            row["excl_agree"] = float(bool(ge) == bool(pe))
        else:
            row["gold_sat@10"] = row["pred_sat@10"] = None
            row["gold_coverage"] = row["pred_coverage"] = float(len(top) > 0)
        rows.append(row)

    with open(OUT / "ablation_rows.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # summary
    agg = defaultdict(lambda: defaultdict(list))
    for r in rows:
        k = r["kind"]
        for key in r:
            if key.endswith("@10") or key.endswith("coverage") or key.endswith("any_viol") \
                    or key.endswith("_agree"):
                if r[key] is not None:
                    agg[k][key].append(r[key])
    print(f"{'kind':<14} {'n':>3} {'gold_sat':>8} {'pred_sat':>8} {'gold_viol':>9} "
          f"{'pred_viol':>9} {'coarse_agree':>11} {'excl_agree':>9}")
    for k in sorted(agg):
        d = agg[k]
        n = len(d.get("gold_sat@10") or d.get("gold_viol@10") or d.get("gold_coverage") or [])
        def m(key):
            v = d.get(key) or []
            return round(sum(v) / len(v), 3) if v else None
        print(f"{k:<14} {n:>3} {str(m('gold_sat@10')):>8} {str(m('pred_sat@10')):>8} "
              f"{str(m('gold_any_viol')):>9} {str(m('pred_any_viol')):>9} "
              f"{str(m('coarse_agree')):>11} {str(m('excl_agree')):>9}")
    print(f"\nwrote {OUT / 'ablation_rows.jsonl'} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
