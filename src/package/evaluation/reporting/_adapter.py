"""Adapt run_agent_eval outputs to the reporting ``results`` shape.

The reporting generators consume a flat ``results`` dict (``summary``,
``request_kinds``, ``metric_values``, ``retrieval_funnel``, ``failures``,
``multi_turn``, ``latency_values``). Real agent-eval artifacts are nested
differently — ``summarize()`` yields agent -> kind -> segment means and
``scored.jsonl`` rows carry per-request metrics. This module bridges the
two without inventing data:

- ``request_kinds`` entries are keyed ``"<agent>/<kind>"`` so the agent
  dimension is never collapsed away.
- Metric stats (mean/std/min/max) are recomputed from scored rows, not
  copied from summary means — ``None`` values are excluded, never zeroed.
- ``layers`` and ``components`` sections are intentionally absent: scored
  rows carry no layer labels and component benchmarks live in a separate
  pipeline. Generators skip missing sections.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

# Fixed headline metrics always offered to the report when present in rows.
# Token/currency columns stay in metrics.json — they are not report metrics.
_HEADLINE_METRICS = (
    "task_success",
    "constraint_satisfaction",
    "exclusion_compliance",
    "tool_selection_ok",
    "asked_clarification",
    "invented_ids",
    "n_steps",
    "first_attempt_ok",
    "reflections",
    "answer_status_ok",
    "answer_grounded",
    "answer_fallback",
)

# Ranking metrics embed k in the column name (precision@10, ndcg@10, ...).
# "spec_" covers spec_* metrics (spec_recall@10, spec_precision@10, ...) from
# package/evaluation/spec/ — Phase 2 backfill metrics.
_DYNAMIC_PREFIXES = ("precision@", "recall@", "hit_rate@", "ndcg@", "mrr@", "map@", "spec_")

_FUNNEL_COLUMNS = (
    "candidate_generation_count",
    "retrieved_count",
    "filtered_count",
    "ranked_count",
    "n_recommended",
)


def _headline_keys(rows: list[dict[str, Any]]) -> list[str]:
    keys = set(_HEADLINE_METRICS)
    for row in rows:
        for key in row:
            if any(key.startswith(p) for p in _DYNAMIC_PREFIXES):
                keys.add(key)
    return sorted(keys)


def _metric_values(rows: list[dict[str, Any]], keys: list[str]) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for key in keys:
        vals = []
        for row in rows:
            v = row.get(key)
            if isinstance(v, (int, float)):
                vals.append(float(v))
        if vals:
            out[key] = vals
    return out


def _group_stats(rows: list[dict[str, Any]], keys: list[str]) -> dict[str, dict[str, float]]:
    """mean/std/min/max/count per metric over non-None numeric values."""
    stats: dict[str, dict[str, float]] = {}
    for key in keys:
        vals = np.array(
            [float(r[key]) for r in rows if isinstance(r.get(key), (int, float))],
            dtype=float,
        )
        if vals.size == 0:
            continue
        stats[key] = {
            "mean": float(np.mean(vals)),
            "std": float(np.std(vals)),
            "min": float(np.min(vals)),
            "max": float(np.max(vals)),
            "count": int(vals.size),
        }
    return stats


def build_report_results(
    rows: list[dict[str, Any]],
    trajectories: list[dict[str, Any]],
    *,
    k: int,
    trajectory_path: str | Path | None = None,
    multi_turn: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the ``results`` dict consumed by reporting generators.

    Args:
        rows: scored rows (one per request x agent)
        trajectories: raw trajectories, used only to attach plan errors
            to failure records
        k: recommendation list size (provenance for the report header)
        trajectory_path: path shown as trace reference in failure records
        multi_turn: optional scalar metrics extracted from multi_turn.json
            (turn_success_rate, conversation_success_rate, context_retention)

    Returns:
        results dict for generate_markdown_report / generate_csv_export /
        generate_failure_report / generate_all_charts
    """
    keys = _headline_keys(rows)

    # request_kinds: one entry per (agent, kind) pair, labelled "agent/kind"
    # so agents sharing a kind never collapse into one row.
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault((str(row.get("agent")), str(row.get("kind"))), []).append(row)
    request_kinds = [
        {"kind": f"{agent}/{kind}", "metrics": _group_stats(group, keys)}
        for (agent, kind), group in sorted(groups.items())
    ]

    # Pooled per-metric value lists drive the CI table and latency chart.
    metric_values = _metric_values(rows, keys)
    latency_values = [
        float(r["wall_seconds"]) for r in rows if isinstance(r.get("wall_seconds"), (int, float))
    ]

    # Mean funnel counts across rows that measured them (None excluded).
    retrieval_funnel: dict[str, float] = {}
    for col in _FUNNEL_COLUMNS:
        vals = [float(r[col]) for r in rows if isinstance(r.get(col), (int, float))]
        if vals:
            retrieval_funnel[col] = float(np.mean(vals))

    # Failures: task_success False or provider_error. stage_lost gives the
    # honest retrieval-stage attribution; trajectory error gives the cause.
    traj_by_key = {
        (t.get("request_id"), t.get("agent")): t for t in trajectories
    }
    failures: list[dict[str, Any]] = []
    for row in rows:
        # task_success is scored as 0.0/1.0/None — falsy-but-not-None counts,
        # None (unmeasurable) never does.
        ts = row.get("task_success")
        failed = (ts is not None and not ts) or row.get("provider_error") is True
        if not failed:
            continue
        traj = traj_by_key.get((row.get("request_id"), row.get("agent"))) or {}
        cause = traj.get("error") or row.get("answer_status") or "task_success=False"
        failures.append(
            {
                "case_id": f"{row.get('agent')}:{row.get('request_id')}",
                "error": str(cause)[:200],
                "failure_stage": row.get("stage_lost") or "unknown",
                "trace_file": str(trajectory_path) if trajectory_path else "",
            }
        )

    results: dict[str, Any] = {
        "summary": {
            "scored_rows": len(rows),
            "requests": len({r.get("request_id") for r in rows}),
            "agents": ", ".join(sorted({str(r.get("agent")) for r in rows})),
            "k": k,
        },
        "request_kinds": request_kinds,
        "metric_values": metric_values,
        "latency_values": latency_values,
        "failures": failures,
    }
    if retrieval_funnel:
        results["retrieval_funnel"] = retrieval_funnel
    if multi_turn:
        results["multi_turn"] = multi_turn
    return results
