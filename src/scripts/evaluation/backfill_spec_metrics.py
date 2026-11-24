"""Phase-2 offline backfill: spec_* metrics on existing agent-eval trajectories.

READ-ONLY wrt artifacts — never modifies scored.jsonl/trajectories.jsonl.
Writes per-request metric rows + aggregates under --out (default
investigations/distill_phase2/).

Usage:
    .venv/Scripts/python scripts/evaluation/backfill_spec_metrics.py \
        --arm baseline=experiments/agent_eval/filter_ab/exp_2_baseline/run_1 \
        --arm f3=experiments/agent_eval/filter_ab/exp_1_always_category/run_1 \
        --baseline baseline

First run builds item_spec_view.parquet (~2.6M rows: item_id, coarse,
ancestor, has_categories) — one streaming pass over item_categories, cached
afterwards.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from package.evaluation.spec import (  # noqa: E402
    COARSE_MIN_ITEMS,
    ItemSpecView,
    category_spec_metrics,
    coarse_label,
    exclusion_spec_metrics,
    paired_bootstrap_diff,
)

CORPUS = "resource/corpus/multi_domain/corpus_multi_domain.sqlite"
ITEM2ID = "resource/mapped/multi_domain/item2id.json"
OUT_DIR = Path("investigations/distill_phase2")
KINDS = ("cold_text", "similar", "exclusion")
TOP_POPULAR = 1000  # popularity baseline pool: top-N by rating_number
PRIMARY = {"cold_text": "spec_precision@10", "similar": "spec_precision@10",
           "exclusion": "spec_violation_rate"}


# ---------------------------------------------------------------- corpus -- #


def label_counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        r[0]: int(r[1])
        for r in conn.execute("SELECT category, COUNT(*) FROM item_categories GROUP BY category")
    }


def _coarse_and_ancestor(seq: list[str], counts: dict[str, int]) -> tuple[str | None, str | None]:
    """coarse_label leaf-up + the label one position above it (depth d-1 probe)."""
    seq = [s for s in seq if s]
    coarse = coarse_label(seq, counts, COARSE_MIN_ITEMS)
    if coarse is None:
        return None, None
    idx = len(seq) - 1 - seq[::-1].index(coarse)
    ancestor = seq[idx - 1] if idx > 0 else None
    return coarse, ancestor


def build_item_views(conn: sqlite3.Connection, out_path: Path) -> pd.DataFrame:
    """Stream item_categories (rowid order = contiguous per-item blocks per C_REPORT)
    and resolve coarse/ancestor per item; uncategorized items get has_categories=False.
    """
    counts = label_counts(conn)
    rows: list[tuple[str, str | None, str | None, int]] = []
    cur_item, seq = None, []

    def flush(item_id: str, labels: list[str]) -> None:
        coarse, ancestor = _coarse_and_ancestor(labels, counts)
        rows.append((item_id, coarse, ancestor, 1))

    for item_id, category in conn.execute(
        "SELECT item_id, category FROM item_categories ORDER BY rowid"
    ):
        if item_id != cur_item:
            if cur_item is not None:
                flush(cur_item, seq)
            cur_item, seq = item_id, []
        seq.append(category)
    if cur_item is not None:
        flush(cur_item, seq)

    df = pd.DataFrame(rows, columns=["item_id", "coarse", "ancestor", "has_categories"])

    # main_category fallback for categorized items whose labels all fall below N
    mc = pd.read_sql_query("SELECT item_id, main_category FROM items", conn)
    need = df["coarse"].isna()
    fb = mc.set_index("item_id")["main_category"]
    df.loc[need, "coarse"] = df.loc[need, "item_id"].map(fb)
    df.loc[need, "ancestor"] = None  # fallback coarse has no taxonomy parent

    # uncategorized items: in items but absent from item_categories.
    # coarse stays None -> strict spec NEVER counts them (lenient variant does).
    have = set(df["item_id"])
    uncat = mc[~mc["item_id"].isin(have)]
    uncat_df = pd.DataFrame(
        {
            "item_id": uncat["item_id"],
            "coarse": None,
            "ancestor": None,
            "has_categories": 0,
        }
    )
    df = pd.concat([df, uncat_df], ignore_index=True)
    df.to_parquet(out_path, index=False)
    return df


def seq_of(conn: sqlite3.Connection, item_id: str) -> list[str]:
    return [
        r[0]
        for r in conn.execute(
            "SELECT category FROM item_categories WHERE item_id = ? ORDER BY rowid", (item_id,)
        )
    ]


def make_lookup(df_indexed: pd.DataFrame, conn: sqlite3.Connection,
                cat_cache: dict[str, frozenset[str]]):
    """item_id -> ItemSpecView | None, lazily attaching full category sets."""
    cache: dict[str, ItemSpecView | None] = {}

    def lookup(iid: str) -> ItemSpecView | None:
        if iid in cache:
            return cache[iid]
        try:
            row = df_indexed.loc[iid]
        except KeyError:
            cache[iid] = None
            return None
        if isinstance(row, pd.DataFrame):  # duplicate item_id (shouldn't happen)
            row = row.iloc[0]
        view = ItemSpecView(
            coarse=row["coarse"], ancestor=row["ancestor"],
            has_categories=bool(row["has_categories"]), categories=None,
        )
        if iid not in cat_cache:
            cat_cache[iid] = frozenset(
                r[0] for r in conn.execute(
                    "SELECT category FROM item_categories WHERE item_id = ?", (iid,)
                )
            )
        cats = cat_cache.get(iid)
        if cats is not None and view.has_categories:
            view = ItemSpecView(view.coarse, view.ancestor, view.has_categories, cats)
        cache[iid] = view
        return view

    return lookup


def gold_for_request(req: dict, conn, counts, idx2item, df_indexed) -> tuple:
    """(gold_coarse, gold_ancestor, excluded_item_ids, excluded_categories).

    cold_text: first target's taxonomy sequence (oracle — request.category is
    itself held-out-derived). similar: seed item sequence (clean).
    exclusion: request fields directly (build_requests.py:117-126).
    """
    kind = req["kind"]
    if kind in ("cold_text", "similar"):
        if kind == "cold_text":
            targets = req.get("targets") or []
            item_id = idx2item.get(targets[0]) if targets else None
        else:
            item_id = req.get("seed_item_id")
        if not item_id:
            return None, None, [], []
        seq = seq_of(conn, item_id)
        coarse, ancestor = _coarse_and_ancestor(seq, counts)
        if coarse is None:
            # uncategorized gold item or all labels < N -> main_category fallback
            try:
                coarse = df_indexed.loc[item_id, "coarse"]
                ancestor = df_indexed.loc[item_id, "ancestor"]
            except KeyError:
                coarse, ancestor = None, None
        return coarse, ancestor, [], []
    if kind == "exclusion":
        return None, None, list(req.get("excluded_item_ids") or []), list(
            req.get("excluded_categories") or []
        )
    return None, None, [], []


# ------------------------------------------------------------- per-arm ---- #


def backfill_arm(arm: str, run_dir: Path, conn, counts, idx2item, df_indexed,
                 lookup) -> list[dict]:
    reqs = {
        r["request_id"]: r
        for r in (json.loads(l) for l in open(run_dir / "requests.jsonl", encoding="utf-8") if l.strip())
    }
    trajs = {
        t["request_id"]: t
        for t in (json.loads(l) for l in open(run_dir / "trajectories.jsonl", encoding="utf-8") if l.strip())
    }
    scored = {}
    sp = run_dir / "scored.jsonl"
    if sp.is_file():
        scored = {
            s["request_id"]: s
            for s in (json.loads(l) for l in open(sp, encoding="utf-8") if l.strip())
        }

    rows = []
    for rid, req in reqs.items():
        if req["kind"] not in KINDS:
            continue
        traj = trajs.get(rid)
        if traj is None:
            rows.append({"arm": arm, "request_id": rid, "kind": req["kind"],
                         "spec_metric_error": "missing_trajectory"})
            continue
        recommended = traj.get("recommended") or []
        gold_coarse, gold_ancestor, ex_ids, ex_cats = gold_for_request(
            req, conn, counts, idx2item, df_indexed
        )
        if req["kind"] == "exclusion":
            metrics = exclusion_spec_metrics(recommended, lookup, ex_ids, ex_cats)
        else:
            metrics = category_spec_metrics(recommended, lookup, gold_coarse, gold_ancestor)
        sc = scored.get(rid, {})
        rows.append({
            "arm": arm,
            "request_id": rid,
            "kind": req["kind"],
            "gold_coarse": gold_coarse,
            "task_success": sc.get("task_success"),
            "target_recall@10": sc.get("recall@10"),
            **metrics,
        })
    return rows


# ------------------------------------------------------------- baselines -- #


def baselines_for(gold_coarse, coarse_counts: Counter, top_pop_coarse: Counter,
                  n_items: int) -> dict[str, float]:
    """Expected spec_precision@10 for trivial strategies over the WHOLE catalog.

    random: E[hits in 10 uniform draws] = 10*|S|/N. popularity: fraction of the
    top-1000 rating_number items resolving to gold_coarse. (Sampling FROM S
    would trivially score 1.0 — meaningless; these measure what the pipeline
    must beat to show the constraint did work.)
    """
    if gold_coarse is None:
        return {"spec_random_baseline@10": 0.0, "spec_popularity_baseline@10": 0.0,
                "spec_set_size": 0.0}
    s = coarse_counts.get(gold_coarse, 0)
    pop = top_pop_coarse.get(gold_coarse, 0)
    return {
        "spec_random_baseline@10": 10.0 * s / max(n_items, 1),
        "spec_popularity_baseline@10": pop / TOP_POPULAR,
        "spec_set_size": float(s),
    }


def mean_of(rows: list[dict], key: str) -> float | None:
    vals = [r[key] for r in rows if r.get(key) is not None]
    return sum(vals) / len(vals) if vals else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", action="append", required=True,
                    help="name=run_dir (repeatable)")
    ap.add_argument("--baseline", default=None, help="arm name for paired diffs")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(f"file:{CORPUS}?mode=ro", uri=True)
    counts = label_counts(conn)

    view_path = args.out / "item_spec_view.parquet"
    if view_path.is_file():
        df = pd.read_parquet(view_path)
        print(f"[cache] {view_path}", flush=True)
    else:
        print("[build] item_spec_view.parquet (one pass over item_categories)...", flush=True)
        df = build_item_views(conn, view_path)
        print(f"[build] done: {len(df)} items", flush=True)

    df_indexed = df.set_index("item_id", drop=False)
    cat_cache: dict[str, frozenset[str]] = {}
    lookup = make_lookup(df_indexed, conn, cat_cache)

    coarse_counts = Counter(
        df.loc[df["has_categories"] == 1, "coarse"].dropna().tolist()
    )
    n_items = int(conn.execute("SELECT COUNT(*) FROM items").fetchone()[0])

    top_ids = [r[0] for r in conn.execute(
        "SELECT item_id FROM items WHERE rating_number IS NOT NULL "
        "ORDER BY rating_number DESC LIMIT ?", (TOP_POPULAR,),
    )]
    top_pop_coarse = Counter()
    for iid in top_ids:
        v = lookup(iid)
        if v and v.coarse:
            top_pop_coarse[v.coarse] += 1

    i2i = json.load(open(ITEM2ID, encoding="utf-8"))
    idx2item = {v: k for k, v in i2i.items()}

    all_rows: list[dict] = []
    for spec_ in args.arm:
        name, run_dir = spec_.split("=", 1)
        run_dir = Path(run_dir)
        if not (run_dir / "trajectories.jsonl").is_file():
            print(f"[skip] {name}: no trajectories.jsonl in {run_dir}", flush=True)
            continue
        rows = backfill_arm(name, run_dir, conn, counts, idx2item, df_indexed, lookup)
        all_rows.extend(rows)
        print(f"[done] {name}: {len(rows)} in-scope requests", flush=True)

    for r in all_rows:
        if "spec_metric_error" in r:
            continue
        r.update(baselines_for(r.get("gold_coarse"), coarse_counts, top_pop_coarse, n_items))
        s = r.get("spec_set_size") or 0
        rec = r.get("target_recall@10")
        r["spec_target_recall_norm@10"] = (
            float(rec) / (10.0 / s) if rec is not None and s > 0 else None
        )

    out_jsonl = args.out / "spec_backfill_rows.jsonl"
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for r in all_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    metric_keys = [
        "task_success", "spec_precision@10", "spec_precision@10_lenient",
        "spec_hit@10", "spec_precision_ancestor@10", "spec_violation_rate",
        "spec_result_coverage", "spec_random_baseline@10",
        "spec_popularity_baseline@10", "spec_target_recall_norm@10",
        "spec_set_size", "spec_n_recommended",
    ]
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in all_rows:
        if "spec_metric_error" not in r:
            groups[(r["arm"], r["kind"])].append(r)

    report: dict[str, dict] = {}
    for (arm, kind), rows in sorted(groups.items()):
        report.setdefault(arm, {})[kind] = {
            "n": len(rows),
            **{m: round(v, 4) for m in metric_keys
               if (v := mean_of(rows, m)) is not None},
        }

    # paired bootstrap diffs vs baseline arm on the primary metric
    if args.baseline:
        base_rows = {(r["request_id"], r["kind"]): r for r in all_rows
                     if r["arm"] == args.baseline and "spec_metric_error" not in r}
        diffs = {}
        for (arm, kind), rows in sorted(groups.items()):
            if arm == args.baseline:
                continue
            key = PRIMARY[kind]
            pairs = [
                (r[key], base_rows[(r["request_id"], r["kind"])][key])
                for r in rows
                if (r["request_id"], r["kind"]) in base_rows
                and r.get(key) is not None
                and base_rows[(r["request_id"], r["kind"])].get(key) is not None
            ]
            if pairs:
                a = [p[0] for p in pairs]
                b = [p[1] for p in pairs]
                diffs[f"{arm}|{kind}"] = {key: paired_bootstrap_diff(a, b)}
        report["_paired_diff_vs_" + args.baseline] = diffs

    (args.out / "spec_backfill_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"saved -> {out_jsonl} + spec_backfill_summary.json", flush=True)


if __name__ == "__main__":
    main()
