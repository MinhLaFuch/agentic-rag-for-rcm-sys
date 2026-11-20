"""Q3: SearchTool timeout profiling.

Engine: SQLite FTS5 (items_fts, porter unicode61) + BM25, JOIN items, ORDER BY
-bm25, rating_number DESC, item_id; plus a separate COUNT(*) MATCH query.
Under eval policy `items` is a temp view masking mutable fields (Q18 bug also
deggrades SearchTool's rating_number tiebreak to item_id order).

Method:
  1. Parse trajectories of exp_5 + union run_1; collect every SearchTool step
     (query, filters, limit, ok, latency_seconds, error_kind, request kind).
  2. On a RAW read-only corpus connection (no eval authorizer), replay the
     exact SELECT (match + no filters) and COUNT for each unique query,
     timing both. Timeout = >5s (tool budget). Also EXPLAIN QUERY PLAN.
  3. Characterize slow vs fast: token count, token corpus frequency
     (avg df via FTS), filter presence.
  4. Check whether timed-out requests still surfaced targets in recorded
     candidate outputs.

Output: investigations/q3_search_timeouts.json
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from package.tools.retrieval._helper import _tokenize  # noqa: E402

RUNS = [
    ROOT / "experiments/agent_eval/campaigns/campaign_005/exp_5_agents_planner_inference_mode_template_reflect_rounds_0_multi_turn_True/run_1",
    ROOT / "experiments/agent_eval/union_ab/exp_1_union_prompt/run_1",
]
DB = "resource/corpus/multi_domain/corpus_multi_domain.sqlite"
OUT = Path(__file__).parent / "q3_search_timeouts.json"
BUDGET_S = 5.0

SELECT_SQL = (
    "SELECT items.item_id, -bm25(items_fts) AS score "
    "FROM items_fts JOIN items ON items.rowid = items_fts.rowid "
    "WHERE items_fts MATCH ? ORDER BY score DESC, items.rating_number DESC, items.item_id LIMIT ?"
)
COUNT_SQL = (
    "SELECT COUNT(*) AS cnt FROM items_fts JOIN items ON items.rowid = items_fts.rowid "
    "WHERE items_fts MATCH ?"
)


def main() -> None:
    # ---- 1. collect SearchTool steps ----
    steps = []
    for run in RUNS:
        reqs = {r["request_id"]: r for r in
                (json.loads(l) for l in open(run / "requests.jsonl", encoding="utf-8"))}
        for tp in run.glob("*trajectories*.jsonl"):
            for line in open(tp, encoding="utf-8"):
                row = json.loads(line)
                req = reqs.get(row.get("request_id"), {})
                targets = set(req.get("targets", []))
                for st in row.get("steps", []):
                    if st.get("tool") != "SearchTool":
                        continue
                    args = st.get("args") or {}
                    data = st.get("data") or {}
                    cands = {c.get("item_id") for c in (data.get("candidates") or [])}
                    steps.append({
                        "run": run.name, "request_id": row.get("request_id"),
                        "kind": req.get("kind"), "query": args.get("query"),
                        "filters": args.get("filters") or {}, "limit": args.get("limit"),
                        "ok": st.get("ok"), "latency": st.get("latency_seconds"),
                        "error_kind": st.get("error_kind"),
                        "n_candidates": len(cands),
                        "target_hits": len(cands & targets),
                        "n_targets": len(targets),
                    })
    print(f"SearchTool steps={len(steps)}", flush=True)
    ok_lat = [s["latency"] for s in steps if s.get("latency")]
    timeouts = [s for s in steps if (s.get("latency") or 0) > BUDGET_S or s.get("error_kind")]
    print(f"steps>5s or error: {len(timeouts)}; latency p50/p90/max = "
          f"{sorted(ok_lat)[len(ok_lat)//2] if ok_lat else None}/"
          f"{sorted(ok_lat)[int(len(ok_lat)*0.9)] if ok_lat else None}/"
          f"{max(ok_lat) if ok_lat else None}", flush=True)

    # ---- 2. replay unique queries on raw conn ----
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    uniq = {}
    for s in steps:
        q = s.get("query")
        if q:
            uniq.setdefault(q, s)
    print(f"unique queries={len(uniq)}", flush=True)

    results = []
    for q, s in uniq.items():
        tokens = _tokenize(q)
        if not tokens:
            continue
        match = " OR ".join(f'"{t}"' for t in tokens)
        rec = {"query": q, "n_tokens": len(tokens), "tokens": tokens,
               "filters": s["filters"], "limit": s.get("limit"),
               "kind": s["kind"], "steps_using": sum(1 for x in steps if x["query"] == q),
               "max_step_latency": max(x["latency"] or 0 for x in steps if x["query"] == q),
               "any_target_hit": any(x["target_hits"] > 0 for x in steps if x["query"] == q)}
        # token document frequency (avg rarity)
        dfs = []
        for t in tokens:
            try:
                dfs.append(conn.execute(
                    "SELECT COUNT(*) FROM items_fts WHERE items_fts MATCH ?", (f'"{t}"',)).fetchone()[0])
            except sqlite3.Error:
                dfs.append(-1)
        rec["token_df_min"] = min(dfs) if dfs else None
        rec["token_df_median"] = float(np.median(dfs)) if dfs else None
        # timed select (no filters — filters only make it slower; note separately)
        t0 = time.perf_counter()
        try:
            rows = conn.execute(SELECT_SQL, (match, int(s.get("limit") or 50))).fetchall()
            rec["select_seconds"] = round(time.perf_counter() - t0, 3)
            rec["select_rows"] = len(rows)
        except sqlite3.Error as e:
            rec["select_seconds"] = None
            rec["select_error"] = str(e)[:200]
        t0 = time.perf_counter()
        try:
            conn.execute(COUNT_SQL, (match,)).fetchall()
            rec["count_seconds"] = round(time.perf_counter() - t0, 3)
        except sqlite3.Error as e:
            rec["count_seconds"] = None
            rec["count_error"] = str(e)[:200]
        results.append(rec)
        print(f"  q={q[:60]!r} tok={rec['n_tokens']} sel={rec.get('select_seconds')}s "
              f"cnt={rec.get('count_seconds')}s", flush=True)

    slow = [r for r in results if (r.get("select_seconds") or 0) > BUDGET_S
            or (r.get("count_seconds") or 0) > BUDGET_S]
    fast = [r for r in results if r not in slow and r.get("select_seconds") is not None]

    def summ(rs):
        if not rs:
            return None
        sels = [r["select_seconds"] for r in rs if r.get("select_seconds") is not None]
        cnts = [r["count_seconds"] for r in rs if r.get("count_seconds") is not None]
        return {
            "n": len(rs),
            "select_s_median": float(np.median(sels)) if sels else None,
            "select_s_max": max(sels) if sels else None,
            "count_s_median": float(np.median(cnts)) if cnts else None,
            "count_s_max": max(cnts) if cnts else None,
            "mean_tokens": float(np.mean([r["n_tokens"] for r in rs])),
            "mean_token_df_median": float(np.mean([r["token_df_median"] or 0 for r in rs])),
            "frac_with_filters": round(sum(1 for r in rs if r["filters"]) / len(rs), 3),
            "frac_target_hit": round(sum(1 for r in rs if r["any_target_hit"]) / len(rs), 3),
        }

    # EXPLAIN for the slowest query
    explain = None
    if slow:
        worst = max(slow, key=lambda r: (r.get("select_seconds") or 0) + (r.get("count_seconds") or 0))
        match = " OR ".join(f'"{t}"' for t in worst["tokens"])
        explain = {
            "query": worst["query"],
            "plan": [list(r) for r in conn.execute(
                "EXPLAIN QUERY PLAN " + SELECT_SQL.replace("LIMIT ?", "LIMIT 50"), (match,))],
        }

    report = {
        "engine": "SQLite FTS5 items_fts (porter unicode61) BM25 + JOIN items; "
                  "separate COUNT(*) MATCH; eval masks rating_number -> item_id tiebreak (Q18)",
        "budget_seconds": BUDGET_S,
        "n_searchtool_steps": len(steps),
        "n_unique_queries": len(results),
        "n_steps_over_budget_or_error": len(timeouts),
        "step_latency": {
            "median": float(np.median(ok_lat)) if ok_lat else None,
            "p90": float(np.percentile(ok_lat, 90)) if ok_lat else None,
            "max": float(max(ok_lat)) if ok_lat else None,
        },
        "replay": {"slow": summ(slow), "fast": summ(fast)},
        "slow_queries": sorted(slow, key=lambda r: -(r.get("select_seconds") or 0))[:15],
        "explain_slowest": explain,
        "per_step": steps,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("n_searchtool_steps", "n_unique_queries",
          "n_steps_over_budget_or_error", "step_latency", "replay")}, indent=2))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
