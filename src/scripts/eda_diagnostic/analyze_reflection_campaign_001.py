"""Read-only reflection analysis on campaign_001 real artifacts (week47 R1/R2).

For exp_6/exp_8 (planner, template/llm, reflect_rounds=1) and
exp_10/exp_12 (planner_memory, template/llm, reflect_rounds=1):

- count reflect-invoked requests, rescued (reflection_succeeded), not rescued
- classify the PERSISTENT failure of not-rescued requests by final step
  error_kind + error-text buckets
- reflect cost: planner usage tokens/latency/attempts for invoked vs not,
  plus paired delta vs the matching reflect_rounds=0 experiment
  (exp_5/exp_7/exp_9/exp_11 — same agent set, same seed=42 -> same request_ids)

KNOWN ARTIFACT LIMIT (reported, not worked around): trajectories store only the
FINAL plan/steps (executor.last_plan + best_results). The pre-reflect attempt —
its failed step and the REFLECT_NOTICE problem string — is NOT persisted
(plan_executor.py:171 keeps last_attempt_plans in memory only; run_agent_eval
writes plan=executor.last_plan). Therefore the INITIAL error type of RESCUED
requests is unrecoverable from artifacts -> R2 can only be bounded, not counted.

Run from src/:
    PYTHONPATH=. python scripts/eda_diagnostic/analyze_reflection_campaign_001.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median

SRC = Path(__file__).resolve().parents[2]
CAMPAIGN = SRC / "experiments" / "agent_eval" / "campaigns" / "campaign_001"

# reflect_rounds=1 experiments under analysis, paired with their r0 sibling
REFLECT_EXPS = {
    "exp_6": ("planner", "template", "exp_5"),
    "exp_8": ("planner", "llm", "exp_7"),
    "exp_10": ("planner_memory", "template", "exp_9"),
    "exp_12": ("planner_memory", "llm", "exp_11"),
}


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _exp_run_dir(exp_prefix: str) -> Path | None:
    matches = sorted(CAMPAIGN.glob(f"{exp_prefix}_*/run_1"))
    return matches[0] if matches else None


def _planner_trajs(run_dir: Path) -> dict[tuple[str, str], dict]:
    """trajectories keyed by (request_id, agent), planner-family agents only."""
    out = {}
    for t in _load_jsonl(run_dir / "trajectories.jsonl"):
        if str(t.get("agent", "")).startswith("planner"):
            out[(t["request_id"], t["agent"])] = t
    return out


def _scored_map(run_dir: Path) -> dict[tuple[str, str], dict]:
    out = {}
    for r in _load_jsonl(run_dir / "scored.jsonl"):
        out[(r["request_id"], r["agent"])] = r
    return out


def classify_error(error: str | None) -> str:
    """Root-cause bucket for a failed step's error text (mirrors
    analyze_campaign_001_planner_errors.classify, extended)."""
    if not error:
        return "no_error_text"
    e = error.lower()
    if "price_range.max" in e and "not found" in e:
        return "ref_null_price_range"
    if "not found in the catalog" in e or "nonexistentcategory" in e:
        return "category_not_in_catalog"
    if "time budget" in e or "sqltimeout" in e:
        return "search_time_budget"
    if "skipped, step" in e:
        return "cascade_skip"
    if "has not run yet" in e or "failed" in e and "step" in e:
        return "bad_reference"
    if "empty" in e and "candidate" in e:
        return "empty_candidates"
    if "invented" in e:
        return "invented_id"
    if "unknown tool" in e:
        return "unknown_tool"
    return "other"


def _failed_step_kinds(traj: dict) -> list[tuple[str | None, str, str]]:
    """(tool, error_kind, bucket) for each failed step of the FINAL attempt."""
    out = []
    for s in traj.get("steps", []):
        if s.get("ok", True) and not s.get("error"):
            continue
        out.append((s.get("tool"), s.get("error_kind"), classify_error(s.get("error"))))
    return out


def _usage(traj: dict) -> dict[str, float]:
    u = traj.get("usage") or {}
    return {
        "attempts": float(u.get("attempts") or 0),
        "prompt_tokens": float(u.get("prompt_tokens") or 0),
        "completion_tokens": float(u.get("completion_tokens") or 0),
        "llm_latency_seconds": float(u.get("latency_seconds") or 0.0),
        "wall_seconds": float(traj.get("wall_seconds") or 0.0),
    }


def _stats(vals: list[float]) -> str:
    if not vals:
        return "n/a"
    return f"mean={mean(vals):.1f} median={median(vals):.1f}"


def analyze_exp(exp: str, agent_label: str, mode: str, r0_exp: str) -> dict:
    run_dir = _exp_run_dir(exp)
    r0_dir = _exp_run_dir(r0_exp)
    if run_dir is None:
        print(f"\n=== {exp} ({agent_label}/{mode}/r1): NO run_1 artifacts")
        return {}
    trajs = _planner_trajs(run_dir)
    scored = _scored_map(run_dir)

    invoked, rescued, not_rescued = [], [], []
    for key, t in trajs.items():
        s = scored.get(key, {})
        if (t.get("reflections") or 0) <= 0:
            continue
        invoked.append((key, t, s))
        if s.get("reflection_succeeded"):
            rescued.append((key, t, s))
        else:
            not_rescued.append((key, t, s))

    print(f"\n=== {exp} ({agent_label}/{mode}/reflect=1) — {len(trajs)} planner trajectories")
    print(f"    reflect invoked : {len(invoked)}")
    print(f"    rescued         : {len(rescued)}")
    print(f"    NOT rescued     : {len(not_rescued)}")

    # --- not rescued: persistent failure classification (FINAL attempt) ---
    kind_counter: Counter = Counter()
    bucket_counter: Counter = Counter()
    empty_persist = 0
    examples: dict[str, list[str]] = defaultdict(list)
    for (rid, agent), t, s in not_rescued:
        fails = _failed_step_kinds(t)
        if not fails:
            empty_persist += 1
            bucket_counter["all_steps_ok_but_no_rec"] += 1
            continue
        for tool, ek, bucket in fails:
            kind_counter[ek or "none"] += 1
            bucket_counter[bucket] += 1
            if len(examples[bucket]) < 3:
                err = next((st.get("error") for st in t["steps"] if st.get("tool") == tool and not st.get("ok", True)), "")
                examples[bucket].append(f"{rid}/{agent}: {tool} ek={ek} err={str(err)[:120]}")
    print("    not-rescued failure kinds (final attempt, may differ from initial):")
    for k, v in kind_counter.most_common():
        print(f"      error_kind={k}: {v}")
    print("    not-rescued error buckets:")
    for k, v in bucket_counter.most_common():
        print(f"      {k}: {v}")
    if empty_persist:
        print(f"      (subset) all final steps ok but recommended empty: {empty_persist}")
    for b, ex in examples.items():
        for e in ex:
            print(f"      [{b}] {e}")

    # --- rescued: trigger type is NOT in artifacts (see module docstring) ---
    rescued_kinds = Counter(s.get("kind") for _, _, s in rescued)
    print(f"    rescued by request kind: {dict(rescued_kinds)}")
    print("    NOTE: initial-error type of rescued requests is unrecoverable "
          "(pre-reflect attempt not persisted) -> R2 bounded only.")

    # --- cost: invoked vs not-invoked within this exp ---
    invoked_rows = [(k, t) for k, t in trajs.items() if (t.get("reflections") or 0) > 0]
    clean_rows = [(k, t) for k, t in trajs.items() if (t.get("reflections") or 0) == 0]
    ci = {m: [_usage(t)[m] for _, t in invoked_rows] for m in _usage({}).keys()}
    cc = {m: [_usage(t)[m] for _, t in clean_rows] for m in _usage({}).keys()}
    print("    cost invoked  : " + "; ".join(f"{k} {_stats(v)}" for k, v in ci.items()))
    print("    cost no-reflect: " + "; ".join(f"{k} {_stats(v)}" for k, v in cc.items()))

    # --- paired delta vs r0 sibling (same request_ids, seed=42) ---
    if r0_dir is not None:
        trajs0 = _planner_trajs(r0_dir)
        deltas = defaultdict(list)
        for key, t in trajs.items():
            t0 = trajs0.get(key)
            if t0 is None:
                continue
            u1, u0 = _usage(t), _usage(t0)
            deltas["prompt_tokens"].append(u1["prompt_tokens"] - u0["prompt_tokens"])
            deltas["completion_tokens"].append(u1["completion_tokens"] - u0["completion_tokens"])
            deltas["llm_latency_seconds"].append(u1["llm_latency_seconds"] - u0["llm_latency_seconds"])
            deltas["attempts"].append(u1["attempts"] - u0["attempts"])
        n_pairs = len(deltas["prompt_tokens"])
        print(f"    paired vs {r0_exp} ({n_pairs} shared requests, r1 minus r0):")
        for k, v in deltas.items():
            print(f"      {k}: {_stats(v)}")
        # reflect-only overhead: restrict to invoked requests
        inv_keys = {k for k, _ in invoked_rows}
        dinv = defaultdict(list)
        for key in inv_keys:
            t0 = trajs0.get(key)
            if t0 is None:
                continue
            u1, u0 = _usage(trajs[key]), _usage(t0)
            for k in ("prompt_tokens", "completion_tokens", "llm_latency_seconds", "attempts"):
                dinv[k].append(u1[k] - u0[k])
        print(f"    paired delta on INVOKED requests only (n={len(dinv['prompt_tokens'])}):")
        for k, v in dinv.items():
            print(f"      {k}: {_stats(v)}")
    else:
        print(f"    paired vs {r0_exp}: NO artifacts")

    return {"invoked": len(invoked), "rescued": len(rescued), "not_rescued": len(not_rescued)}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print("Reflection analysis — campaign_001, real artifacts (read-only)\n")
    for exp, (agent, mode, r0) in REFLECT_EXPS.items():
        analyze_exp(exp, agent, mode, r0)


if __name__ == "__main__":
    main()
