"""Memory UTILITY analysis: paired, multi-run comparison planner vs planner_memory.

Input = `scored.jsonl` (+ `config.yaml`) of N >= 2 agent_eval experiment directories produced by
scripts/evaluation/run_agent_eval.py (each run contains both agents on the SAME requests).
This module does NOT call an LLM; it only analyses runs that already exist.

Design rules (why the numbers are trustworthy / what they are NOT):
- Paired: only requests scored for BOTH conditions are compared; unpaired ones are counted
  and reported (`n_unscored`), never silently dropped.
- Multi-run: each request's value is first averaged over runs per condition; the CI is a
  bootstrap over REQUESTS (the independent unit), so more runs reduce LLM noise but do not
  fake a bigger sample. Run-to-run std is reported next to the diff.
- ORACLE groups (kinds built from held-out targets: constrained, cold_text) are analysed
  separately from realistic ones and are never merged into any overall number.
- Verdicts are per group and conservative: "inconclusive" unless n >= min_n, runs >= 2 and the
  CI excludes 0. No global "memory improves quality" statement is ever produced.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from package.evaluation import ORACLE_KINDS
from package.evaluation.ablation import bootstrap_ci, check_compatibility, load_config_data, load_scored_data

BINARY_METRICS = {"task_success", "first_attempt_ok", "tool_selection_ok"}
COST_METRICS = {"completion_tokens", "prompt_tokens", "llm_latency_seconds", "tool_latency_seconds", "wall_seconds"}


def default_metrics(k: int) -> list[str]:
    return ["task_success", f"recall@{k}", f"ndcg@{k}", "constraint_satisfaction", "first_attempt_ok",
            "completion_tokens", "llm_latency_seconds"]


def scope_of(kind: str) -> str:
    return "oracle" if kind in ORACLE_KINDS else "realistic"


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def _std(xs: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def collect(runs: list[list[dict[str, Any]]], agent: str, metric: str) -> tuple[dict[str, list[float]], dict[str, dict]]:
    """request_id -> list of per-run values (None values skipped); request_id -> {kind, segment}."""
    vals: dict[str, list[float]] = defaultdict(list)
    info: dict[str, dict] = {}
    seen: set[str] = set()
    for scored in runs:
        for r in scored:
            if r.get("agent") != agent:
                continue
            rid = r["request_id"]
            seen.add(rid)
            info[rid] = {"kind": r["kind"], "segment": r["segment"]}
            v = r.get(metric)
            if v is not None:
                vals[rid].append(float(v))
    for rid in seen:
        vals.setdefault(rid, [])
    return vals, info


def analyze_metric(
    runs_a: list[list[dict]], runs_b: list[list[dict]], agent_a: str, agent_b: str, metric: str,
    *, resamples: int = 5000, confidence: float = 0.95, seed: int = 42, min_n: int = 20,
) -> dict[str, dict[str, Any]]:
    """Returns {group_label: stats}. Groups: scope, scope/kind, scope/kind/segment."""
    va, ia = collect(runs_a, agent_a, metric)
    vb, ib = collect(runs_b, agent_b, metric)
    info = {**ia, **ib}
    all_ids = sorted(set(va) | set(vb))

    buckets: dict[str, list[str]] = defaultdict(list)
    for rid in all_ids:
        kind, seg = info[rid]["kind"], info[rid]["segment"]
        sc = scope_of(kind)
        for label in (sc, f"{sc}/{kind}", f"{sc}/{kind}/{seg}"):
            buckets[label].append(rid)

    out: dict[str, dict[str, Any]] = {}
    for label, ids in sorted(buckets.items()):
        paired = [rid for rid in ids if va.get(rid) and vb.get(rid)]
        n_unscored_a = sum(1 for rid in ids if not va.get(rid))
        n_unscored_b = sum(1 for rid in ids if not vb.get(rid))
        st: dict[str, Any] = {
            "scope": label.split("/")[0], "n_requests": len(ids), "n_paired": len(paired),
            "n_unscored_baseline": n_unscored_a, "n_unscored_memory": n_unscored_b,
            "runs_baseline": len(runs_a), "runs_memory": len(runs_b), "warnings": [],
        }
        if st["scope"] == "oracle":
            st["warnings"].append("ORACLE requests (built from held-out targets): upper bound, not a real query log")
        if n_unscored_a or n_unscored_b:
            st["warnings"].append(
                f"{n_unscored_a} request(s) unscored for baseline, {n_unscored_b} for memory "
                "(e.g. personalized is not scored for a planner without MemoryTool): excluded from the pair")
        if not paired:
            st["verdict"] = "no_pairs"
            out[label] = st
            continue
        ma = [_mean(va[r]) for r in paired]
        mb = [_mean(vb[r]) for r in paired]
        diffs = [b - a for a, b in zip(ma, mb)]
        lo, hi = bootstrap_ci(diffs, resamples, confidence, seed)
        sd_a = [s for s in (_std(va[r]) for r in paired) if s is not None]
        sd_b = [s for s in (_std(vb[r]) for r in paired) if s is not None]
        st.update({
            "mean_baseline": _mean(ma), "mean_memory": _mean(mb), "diff": _mean(diffs),
            "ci_lower": lo, "ci_upper": hi, "confidence": confidence,
            "run_std_baseline": _mean(sd_a) if sd_a else None,
            "run_std_memory": _mean(sd_b) if sd_b else None,
            "wins": sum(d > 1e-12 for d in diffs), "losses": sum(d < -1e-12 for d in diffs),
            "ties": sum(abs(d) <= 1e-12 for d in diffs),
        })
        if len(paired) < min_n:
            st["warnings"].append(f"n={len(paired)} < {min_n}: too few pairs for a reliable estimate")
        if min(len(runs_a), len(runs_b)) < 2:
            st["warnings"].append("single run per condition: run-to-run variance not estimable")
        reliable = len(paired) >= min_n and min(len(runs_a), len(runs_b)) >= 2
        if metric in COST_METRICS:
            better_when = "lower"
        else:
            better_when = "higher"
        if not reliable or lo <= 0 <= hi:
            st["verdict"] = "inconclusive"
        else:
            positive = lo > 0
            good = positive if better_when == "higher" else not positive
            st["verdict"] = "memory_better" if good else "memory_worse"
        out[label] = st
    return out


def analyze(
    runs_a: list[list[dict]], runs_b: list[list[dict]], agent_a: str, agent_b: str, metrics: list[str], **kw: Any,
) -> dict[str, dict[str, dict[str, Any]]]:
    return {m: analyze_metric(runs_a, runs_b, agent_a, agent_b, m, **kw) for m in metrics}


def render_markdown(result: dict, meta: dict[str, Any]) -> str:
    L = ["# Memory utility (paired, multi-run)", ""]
    L.append(f"- baseline agent: `{meta['agent_a']}`, memory agent: `{meta['agent_b']}`")
    L.append(f"- runs: baseline={meta['runs_a']}, memory={meta['runs_b']}; seed={meta.get('seed')}; "
             f"bootstrap={meta.get('resamples')} x {meta.get('confidence')}; min_n={meta.get('min_n')}")
    for w in meta.get("compat_warnings", []):
        L.append(f"- WARNING config: {w}")
    L += ["", "REALISTIC and ORACLE groups are reported separately and must not be averaged together.",
          "Verdicts are per group; `inconclusive` is the default.", ""]
    for metric, groups in result.items():
        L += [f"## {metric}", "",
              "| group | n_pairs | unscored (base/mem) | baseline | memory | diff [CI] | run-std (b/m) | W/L/T | verdict |",
              "|---|---|---|---|---|---|---|---|---|"]
        for label, g in groups.items():
            if "diff" not in g:
                L.append(f"| {label} | 0 | {g['n_unscored_baseline']}/{g['n_unscored_memory']} | - | - | - | - | - | {g['verdict']} |")
                continue
            f = lambda x: "n/a" if x is None else f"{x:.3f}"
            L.append(f"| {label} | {g['n_paired']} | {g['n_unscored_baseline']}/{g['n_unscored_memory']} | "
                     f"{g['mean_baseline']:.3f} | {g['mean_memory']:.3f} | {g['diff']:+.3f} "
                     f"[{g['ci_lower']:+.3f}, {g['ci_upper']:+.3f}] | {f(g['run_std_baseline'])}/{f(g['run_std_memory'])} | "
                     f"{g['wins']}/{g['losses']}/{g['ties']} | {g['verdict']} |")
        warns = sorted({w for g in groups.values() for w in g["warnings"]})
        if warns:
            L += [""] + [f"> {w}" for w in warns]
        L.append("")
    return "\n".join(L)


def _load_runs(dirs: list[str]) -> tuple[list[list[dict]], list[dict]]:
    scored, cfgs = [], []
    for d in dirs:
        p = Path(d)
        scored.append(load_scored_data(p))
        try:
            cfgs.append(load_config_data(p))
        except Exception:  # config optional for analysis; compatibility check is skipped
            pass
    return scored, cfgs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dirs", nargs="+", help="experiment dirs; each holds BOTH agents (one run per dir)")
    ap.add_argument("--baseline-dirs", nargs="+", help="override: dirs for the baseline agent")
    ap.add_argument("--memory-dirs", nargs="+", help="override: dirs for the memory agent")
    ap.add_argument("--baseline-agent", default="planner")
    ap.add_argument("--memory-agent", default="planner_memory")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--metrics", nargs="*")
    ap.add_argument("--resamples", type=int, default=5000)
    ap.add_argument("--confidence", type=float, default=0.95)
    ap.add_argument("--min-n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-dir", default=".")
    args = ap.parse_args(argv)

    a_dirs = args.baseline_dirs or args.dirs
    b_dirs = args.memory_dirs or args.dirs
    if not a_dirs or not b_dirs:
        ap.error("give --dirs, or both --baseline-dirs and --memory-dirs")
    runs_a, cfg_a = _load_runs(a_dirs)
    runs_b, cfg_b = _load_runs(b_dirs)

    compat: list[str] = []
    ref = (cfg_a or cfg_b or [None])[0]
    if ref is not None:
        for i, c in enumerate(cfg_a + cfg_b):
            ok, why = check_compatibility(ref, c)
            if not ok:
                compat.append(f"run #{i} incompatible with first run: {why}")

    metrics = args.metrics or default_metrics(args.k)
    kw = dict(resamples=args.resamples, confidence=args.confidence, seed=args.seed, min_n=args.min_n)
    result = analyze(runs_a, runs_b, args.baseline_agent, args.memory_agent, metrics, **kw)
    meta = {"agent_a": args.baseline_agent, "agent_b": args.memory_agent, "runs_a": len(runs_a),
            "runs_b": len(runs_b), "compat_warnings": compat, "dirs_a": a_dirs, "dirs_b": b_dirs, **kw}

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "memory_utility.json").write_text(json.dumps({"meta": meta, "result": result}, indent=2), encoding="utf-8")
    md = render_markdown(result, meta)
    (out / "memory_utility.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
