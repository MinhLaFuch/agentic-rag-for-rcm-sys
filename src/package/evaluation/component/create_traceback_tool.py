"""Attribute end-to-end trajectory failures to pipeline components.

Real implementation: consumes scored rows (``scored.jsonl``) which carry
``component_failure_diagnosis`` — per-tool failure counts with error kinds
produced by layer-4 trajectory scoring — and, when provided, raw trajectories
(``trajectories.jsonl``) to locate the first failing step.

Attribution levels:
- ``tool``: the tool whose step failed (from ``component_failure_diagnosis``).
- ``component``: the benchmark-aligned component group the failure maps to
  (planner / memory / executor / grounding / integration). This mapping is a
  grouping convenience, not a causal claim.

Confidence is derived from observed counts (failures relative to steps), not
assigned arbitrarily.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

# Benchmark-aligned component groups for the agent pipeline.
TOOL_TO_COMPONENT: dict[str, str] = {
    "MemoryTool": "memory",
    "SearchTool": "executor",
    "FilterTool": "executor",
    "SimilarTool": "executor",
    "RankTool": "executor",
    "LookupTool": "executor",
}

def _is_failure(row: dict[str, Any]) -> bool:
    """A scored row counts as failed when task success is falsy or a tool
    failure was diagnosed."""
    if row.get("task_success") is False:
        return True
    diag = row.get("component_failure_diagnosis") or {}
    return any((v or {}).get("total_failures", 0) > 0 for v in diag.values())


def _row_components(row: dict[str, Any]) -> list[str]:
    """Component groups implicated by request-level failure signals."""
    components: list[str] = []
    if row.get("plan_valid") is False:
        components.append("planner")
    if row.get("invented_ids"):
        components.append("planner")
    if row.get("plan_truncated"):
        components.append("planner")
    if row.get("answer_fallback") or row.get("answer_grounded") is False:
        components.append("grounding")
    return components


def _first_failing_step(traj: dict[str, Any] | None) -> dict[str, Any] | None:
    if not traj:
        return None
    for step in traj.get("steps") or []:
        if step.get("ok") is False:
            return step
    return None


def create_traceback_tool(
    scored_rows: list[dict[str, Any]],
    output_path: Path,
    trajectories: list[dict[str, Any]] | None = None,
) -> None:
    """Build a failure-attribution report from scored rows.

    Args:
        scored_rows: Rows from ``scored.jsonl`` (one per request). Each may
            contain ``component_failure_diagnosis`` (per-tool failure counts),
            ``component_states``, ``task_success``, ``plan_valid``,
            ``invented_ids``, ``plan_truncated``, ``answer_fallback``,
            ``answer_grounded``.
        output_path: Path to write the JSON attribution report.
        trajectories: Optional rows from ``trajectories.jsonl``; used to
            record the first failing step per request.
    """
    traj_by_id = {t.get("request_id"): t for t in (trajectories or [])}

    failed_rows = [r for r in scored_rows if _is_failure(r)]

    # Aggregate per-tool and per-component failure counts across all rows.
    tool_failures: Counter[str] = Counter()
    component_failures: Counter[str] = Counter()
    error_kinds: dict[str, Counter[str]] = {}

    attributions: list[dict[str, Any]] = []
    for row in failed_rows:
        request_id = row.get("request_id", "unknown")
        diag = row.get("component_failure_diagnosis") or {}

        implicated_tools: list[str] = []
        for tool, info in diag.items():
            n = (info or {}).get("total_failures", 0)
            if n <= 0:
                continue
            implicated_tools.append(tool)
            tool_failures[tool] += n
            component_failures[TOOL_TO_COMPONENT.get(tool, "executor")] += n
            kinds = error_kinds.setdefault(tool, Counter())
            for kind, cnt in (info.get("error_kinds") or {}).items():
                kinds[kind] += cnt

        implicated_components = sorted(
            {TOOL_TO_COMPONENT.get(t, "executor") for t in implicated_tools}
            | set(_row_components(row))
        )

        traj = traj_by_id.get(request_id)
        first_step = _first_failing_step(traj)
        n_steps = len((traj or {}).get("steps") or [])
        n_fail = sum(
            (info or {}).get("total_failures", 0) for info in diag.values()
        )
        confidence = round(min(1.0, n_fail / max(1, n_steps)), 3) if n_steps else 0.0

        attributions.append(
            {
                "request_id": request_id,
                "agent": row.get("agent"),
                "kind": row.get("kind"),
                "answer_status": row.get("answer_status"),
                "task_success": row.get("task_success"),
                "implicated_tools": implicated_tools,
                "implicated_components": implicated_components,
                "tool_failures": {
                    t: (diag.get(t) or {}) for t in implicated_tools
                },
                "first_failing_step": (
                    {
                        "tool": first_step.get("tool"),
                        "error": first_step.get("error"),
                    }
                    if first_step
                    else None
                ),
                "n_steps": n_steps,
                "confidence": confidence,
            }
        )

    # Requests that failed with no diagnosed tool failure still get an entry
    # when request-level signals exist (e.g. plan invalid, ungrounded answer).
    attributed_ids = {a["request_id"] for a in attributions}
    for row in scored_rows:
        rid = row.get("request_id", "unknown")
        if rid in attributed_ids:
            continue
        comps = _row_components(row)
        if not comps and row.get("task_success") is not False:
            continue
        attributed_ids.add(rid)
        traj = traj_by_id.get(rid)
        first_step = _first_failing_step(traj)
        attributions.append(
            {
                "request_id": rid,
                "agent": row.get("agent"),
                "kind": row.get("kind"),
                "answer_status": row.get("answer_status"),
                "task_success": row.get("task_success"),
                "implicated_tools": [],
                "implicated_components": comps or ["integration"],
                "tool_failures": {},
                "first_failing_step": (
                    {
                        "tool": first_step.get("tool"),
                        "error": first_step.get("error"),
                    }
                    if first_step
                    else None
                ),
                "n_steps": len((traj or {}).get("steps") or []),
                "confidence": 0.0,
            }
        )

    report = {
        "method": "scored_row_component_diagnosis",
        "status": "computed_from_trajectory_diagnostics",
        "total_requests": len(scored_rows),
        "failed_requests": len(failed_rows),
        "attributions": attributions,
        "summary": {
            "tool_failures": dict(tool_failures.most_common()),
            "component_failures": dict(component_failures.most_common()),
            "error_kinds_by_tool": {
                tool: dict(kinds) for tool, kinds in error_kinds.items()
            },
        },
        "tool_to_component_map": TOOL_TO_COMPONENT,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        f"Traceback analysis saved to: {output_path} "
        f"({len(attributions)} attributions from {len(failed_rows)} failed requests)"
    )
