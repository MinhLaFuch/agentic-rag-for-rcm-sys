"""Analyze a single metric comparing two agents."""

from __future__ import annotations

import math
from typing import Any

from package.evaluation.ablation import bootstrap_ci

from .collect import collect


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def _std(xs: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _group_key(info: dict[str, dict], rid: str, level: int) -> str:
    kind = info[rid]["kind"]
    segment = info[rid]["segment"]
    scope = "oracle" if kind in ("constrained", "cold_text") else "realistic"
    if level == 0:
        return scope
    elif level == 1:
        return f"{scope}/{kind}"
    return f"{scope}/{kind}/{segment}"


def _single_run_result(rids: list[str], va: dict[str, list[float]], vb: dict[str, list[float]]) -> dict[str, Any]:
    """Return result for single run - verdict is always inconclusive."""
    paired_a = []
    paired_b = []
    for rid in rids:
        if va[rid] and vb[rid]:
            paired_a.append(_mean(va[rid]))
            paired_b.append(_mean(vb[rid]))
    n_paired = len(paired_a)
    n_unscored_a = sum(1 for rid in rids if not va[rid])
    n_unscored_b = sum(1 for rid in rids if not vb[rid])
    return {
        "n_paired": n_paired,
        "n_unscored_baseline": n_unscored_a,
        "n_unscored_memory": n_unscored_b,
        "mean_baseline": _mean(paired_a) if paired_a else None,
        "mean_memory": _mean(paired_b) if paired_b else None,
        "diff": (_mean(paired_b) - _mean(paired_a)) if paired_a else None,
        "ci_lower": None,
        "ci_upper": None,
        "run_std_baseline": None,
        "run_std_memory": None,
        "wins": sum(1 for a, b in zip(paired_a, paired_b) if b > a),
        "losses": sum(1 for a, b in zip(paired_a, paired_b) if b < a),
        "ties": len(paired_a) - sum(1 for a, b in zip(paired_a, paired_b) if b > a) - sum(1 for a, b in zip(paired_a, paired_b) if b < a),
        "verdict": "inconclusive",
        "warnings": ["single run: CI requires multiple runs"],
    }


def _no_pairs_result(rids: list[str], va: dict[str, list[float]], vb: dict[str, list[float]]) -> dict[str, Any]:
    """Return result when there are no paired requests."""
    n_unscored_a = sum(1 for rid in rids if not va[rid])
    n_unscored_b = sum(1 for rid in rids if not vb[rid])
    return {
        "n_paired": 0,
        "n_unscored_baseline": n_unscored_a,
        "n_unscored_memory": n_unscored_b,
        "mean_baseline": None,
        "mean_memory": None,
        "diff": None,
        "ci_lower": None,
        "ci_upper": None,
        "run_std_baseline": None,
        "run_std_memory": None,
        "wins": 0,
        "losses": 0,
        "ties": 0,
        "verdict": "no_pairs",
        "warnings": [],
    }


def _insufficient_n_result(rids: list[str], va: dict[str, list[float]], vb: dict[str, list[float]],
                           paired_a: list[float], paired_b: list[float], min_n: int) -> dict[str, Any]:
    """Return result when paired data is insufficient for CI."""
    n_paired = len(paired_a)
    n_unscored_a = sum(1 for rid in rids if not va[rid])
    n_unscored_b = sum(1 for rid in rids if not vb[rid])
    return {
        "n_paired": n_paired,
        "n_unscored_baseline": n_unscored_a,
        "n_unscored_memory": n_unscored_b,
        "mean_baseline": _mean(paired_a) if paired_a else None,
        "mean_memory": _mean(paired_b) if paired_b else None,
        "diff": (_mean(paired_b) - _mean(paired_a)) if paired_a else None,
        "ci_lower": None,
        "ci_upper": None,
        "run_std_baseline": _std(paired_a) if paired_a else None,
        "run_std_memory": _std(paired_b) if paired_b else None,
        "wins": sum(1 for a, b in zip(paired_a, paired_b) if b > a),
        "losses": sum(1 for a, b in zip(paired_a, paired_b) if b < a),
        "ties": len(paired_a) - sum(1 for a, b in zip(paired_a, paired_b) if b > a) - sum(1 for a, b in zip(paired_a, paired_b) if b < a),
        "verdict": "inconclusive",
        "warnings": [f"too few pairs: n_paired={n_paired} < min_n={min_n}"],
    }


def _normal_result(rids: list[str], va: dict[str, list[float]], vb: dict[str, list[float]],
                   paired_a: list[float], paired_b: list[float], resamples: int, confidence: float, seed: int,
                   group_label: str, metric: str = "", runs_a: list[list[dict]] | None = None,
                   runs_b: list[list[dict]] | None = None, agent_a: str = "", agent_b: str = "",
                   n_runs: int = 1) -> dict[str, Any]:
    """Normal analysis with sufficient data."""
    n_paired = len(paired_a)
    n_unscored_a = sum(1 for rid in rids if not va[rid])
    n_unscored_b = sum(1 for rid in rids if not vb[rid])

    mean_a = _mean(paired_a)
    mean_b = _mean(paired_b)
    diff = mean_b - mean_a

    diff_values = [b - a for a, b in zip(paired_a, paired_b)]
    ci = bootstrap_ci(diff_values, n_resamples=resamples, confidence=confidence, seed=seed)
    wins = sum(1 for a, b in zip(paired_a, paired_b) if b > a)
    losses = sum(1 for a, b in zip(paired_a, paired_b) if b < a)
    ties = n_paired - wins - losses

    # Compute run-level standard deviation (std of per-run averages across requests in this group)
    if runs_a and runs_b and agent_a and agent_b and n_runs > 1:
        # Compute per-run averages for this group
        run_means_a = []
        run_means_b = []
        for run_idx in range(n_runs):
            run_vals_a = []
            run_vals_b = []
            for rid in rids:
                # Find the value for this run and request
                for req in runs_a[run_idx]:
                    if req.get("agent") == agent_a and req.get("request_id") == rid:
                        v = req.get(metric)
                        if v is not None:
                            run_vals_a.append(float(v))
                        break
                for req in runs_b[run_idx]:
                    if req.get("agent") == agent_b and req.get("request_id") == rid:
                        v = req.get(metric)
                        if v is not None:
                            run_vals_b.append(float(v))
                        break
            if run_vals_a:
                run_means_a.append(_mean(run_vals_a))
            if run_vals_b:
                run_means_b.append(_mean(run_vals_b))
        std_a = _std(run_means_a)
        std_b = _std(run_means_b)
    else:
        # Fallback to per-request std
        std_a = _std(paired_a)
        std_b = _std(paired_b)

    # Determine if this is a cost metric (lower is better)
    is_cost_metric = any(keyword in metric.lower() for keyword in ("token", "cost", "latency", "time"))

    # For cost metrics, positive diff means memory is worse
    if is_cost_metric:
        if ci[0] > 0:
            verdict = "memory_worse"
        elif ci[1] < 0:
            verdict = "memory_better"
        else:
            verdict = "inconclusive"
    else:
        if ci[0] > 0:
            verdict = "memory_better"
        elif ci[1] < 0:
            verdict = "memory_worse"
        else:
            verdict = "inconclusive"

    warnings = []
    if len(paired_a) < 2:
        warnings.append("only 1 paired request: CI may be unreliable")
    if group_label.startswith("oracle"):
        warnings.append("ORACLE scope: category/price from held-out items; upper bound only")
    return {
        "n_paired": n_paired,
        "n_unscored_baseline": n_unscored_a,
        "n_unscored_memory": n_unscored_b,
        "mean_baseline": mean_a,
        "mean_memory": mean_b,
        "diff": diff,
        "ci_lower": ci[0],
        "ci_upper": ci[1],
        "run_std_baseline": std_a,
        "run_std_memory": std_b,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "verdict": verdict,
        "warnings": warnings,
    }


def _analyze_group(
    rids: list[str],
    va: dict[str, list[float]],
    vb: dict[str, list[float]],
    *,
    resamples: int,
    confidence: float,
    seed: int,
    min_n: int,
    n_runs: int,
    group_label: str = "",
    metric: str = "",
    runs_a: list[list[dict]] | None = None,
    runs_b: list[list[dict]] | None = None,
    agent_a: str = "",
    agent_b: str = "",
) -> dict[str, Any]:
    # Check for single run first - can't compute meaningful CI
    if n_runs < 2:
        return _single_run_result(rids, va, vb)

    # Collect paired data
    paired_a = []
    paired_b = []
    for rid in rids:
        if va[rid] and vb[rid]:
            paired_a.append(_mean(va[rid]))
            paired_b.append(_mean(vb[rid]))
    n_paired = len(paired_a)

    # Check for no paired data
    if n_paired == 0:
        return _no_pairs_result(rids, va, vb)

    # Check for insufficient paired data
    if n_paired < min_n:
        return _insufficient_n_result(rids, va, vb, paired_a, paired_b, min_n)

    # Normal analysis with sufficient data
    return _normal_result(rids, va, vb, paired_a, paired_b, resamples, confidence, seed, group_label, metric, runs_a, runs_b, agent_a, agent_b, n_runs)


def analyze_metric(
    runs_a: list[list[dict]], runs_b: list[list[dict]], agent_a: str, agent_b: str, metric: str,
    *, resamples: int = 5000, confidence: float = 0.95, seed: int = 42, min_n: int = 20,
) -> dict[str, dict[str, Any]]:
    """Returns {group_label: stats}. Groups: scope, scope/kind, scope/kind/segment."""
    va, ia = collect(runs_a, agent_a, metric)
    vb, ib = collect(runs_b, agent_b, metric)
    info = {**ia, **ib}
    all_rids = sorted(va.keys() | vb.keys())

    n_runs = max(len(runs_a), len(runs_b))

    groups: dict[str, list[str]] = {}
    for rid in all_rids:
        for level in range(3):
            label = _group_key(info, rid, level)
            groups.setdefault(label, []).append(rid)

    result = {}
    for label, rids in groups.items():
        result[label] = _analyze_group(
            rids, va, vb,
            resamples=resamples, confidence=confidence, seed=seed, min_n=min_n,
            n_runs=n_runs, group_label=label, metric=metric,
            runs_a=runs_a, runs_b=runs_b, agent_a=agent_a, agent_b=agent_b
        )
    return result