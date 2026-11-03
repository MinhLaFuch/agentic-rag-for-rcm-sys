"""Analyze a single metric comparing two agents."""

from __future__ import annotations

import math
from typing import Any

from package.evaluation.ablation._statistics import bootstrap_ci

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


def _analyze_group(
    rids: list[str],
    va: dict[str, list[float]],
    vb: dict[str, list[float]],
    *,
    resamples: int,
    confidence: float,
    seed: int,
    min_n: int,
) -> dict[str, Any]:
    paired_a = []
    paired_b = []
    for rid in rids:
        if va[rid] and vb[rid]:
            paired_a.append(_mean(va[rid]))
            paired_b.append(_mean(vb[rid]))
    n_paired = len(paired_a)
    n_unscored_a = sum(1 for rid in rids if not va[rid])
    n_unscored_b = sum(1 for rid in rids if not vb[rid])

    if n_paired < min_n:
        return {
            "n_paired": n_paired,
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
            "verdict": "insufficient_n",
            "warnings": [f"n_paired={n_paired} < min_n={min_n}"],
        }

    mean_a = _mean(paired_a)
    mean_b = _mean(paired_b)
    diff = mean_b - mean_a

    ci = bootstrap_ci(paired_a, paired_b, resamples=resamples, confidence=confidence, seed=seed)
    wins = sum(1 for a, b in zip(paired_a, paired_b) if b > a)
    losses = sum(1 for a, b in zip(paired_a, paired_b) if b < a)
    ties = n_paired - wins - losses

    std_a = _std([x for x in paired_a])
    std_b = _std([x for x in paired_b])

    if ci[0] > 0:
        verdict = "memory_better"
    elif ci[1] < 0:
        verdict = "memory_worse"
    else:
        verdict = "inconclusive"

    warnings = []
    if len(paired_a) < 2:
        warnings.append("only 1 paired request: CI may be unreliable")
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


def analyze_metric(
    runs_a: list[list[dict]], runs_b: list[list[dict]], agent_a: str, agent_b: str, metric: str,
    *, resamples: int = 5000, confidence: float = 0.95, seed: int = 42, min_n: int = 20,
) -> dict[str, dict[str, Any]]:
    """Returns {group_label: stats}. Groups: scope, scope/kind, scope/kind/segment."""
    va, ia = collect(runs_a, agent_a, metric)
    vb, ib = collect(runs_b, agent_b, metric)
    info = {**ia, **ib}
    all_rids = sorted(va.keys() | vb.keys())

    groups: dict[str, list[str]] = {}
    for rid in all_rids:
        for level in range(3):
            label = _group_key(info, rid, level)
            groups.setdefault(label, []).append(rid)

    result = {}
    for label, rids in groups.items():
        result[label] = _analyze_group(
            rids, va, vb,
            resamples=resamples, confidence=confidence, seed=seed, min_n=min_n
        )
    return result