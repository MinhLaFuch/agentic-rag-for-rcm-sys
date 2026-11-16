"""Link component benchmark results with end-to-end trajectory results.

Real implementation:

- Extracts per-case metrics from each component benchmark JSON
  (``per_case_results``).
- Extracts per-request metrics from e2e scored rows (``scored.jsonl`` rows
  passed via ``e2e_results["scored"]``).
- Matches component cases to e2e requests on ``request_id`` (component cases
  may carry ``request_id`` or use ``case_id`` as the join key).
- Computes Pearson correlation between component case ``success`` and e2e
  ``task_success`` over matched request IDs — only when enough pairs exist.

Honesty contract: when component and e2e request populations do not overlap,
the report says ``insufficient_overlap`` with counts instead of fabricating a
correlation. Component benchmarks run on synthetic cases and e2e runs on
eval requests, so overlap is expected to be zero unless benchmarks are run on
the e2e request set.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

MIN_PAIRS_FOR_CORRELATION = 3


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def _case_request_id(case: dict[str, Any]) -> str | None:
    return case.get("request_id") or case.get("case_id")


def _component_cases(data: dict[str, Any]) -> list[dict[str, Any]]:
    return data.get("per_case_results") or []


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def link_component_to_e2e(
    component_results: dict[str, str],
    e2e_results: dict[str, Any],
    output_path: Path,
) -> None:
    """
    Link component benchmark results with end-to-end trajectory results.

    Args:
        component_results: Dict mapping component name to result JSON file path
        e2e_results: Dict with optional keys:
            - ``scored``: list of scored.jsonl rows (per-request e2e metrics)
            - ``metrics``: run-level summary metrics
            - ``agent``/``run``: identifiers for the e2e arm
        output_path: Path to save linked analysis
    """
    # Load component results
    component_data: dict[str, dict[str, Any]] = {}
    for component, result_file in component_results.items():
        if result_file and Path(result_file).exists():
            with open(result_file, "r", encoding="utf-8") as f:
                component_data[component] = json.load(f)

    scored_rows: list[dict[str, Any]] = e2e_results.get("scored") or []
    e2e_by_request = {
        r.get("request_id"): r for r in scored_rows if r.get("request_id")
    }

    analysis: dict[str, Any] = {
        "component_scores": {},
        "e2e": {
            "agent": e2e_results.get("agent"),
            "run": e2e_results.get("run"),
            "summary_metrics": e2e_results.get("metrics", {}),
            "n_scored_requests": len(scored_rows),
        },
        "linking": {},
    }

    # Extract mean scores per component and attempt request-level matching.
    for component, data in component_data.items():
        cases = _component_cases(data)

        all_metrics: dict[str, list[float]] = {}
        case_success: list[float] = []
        matched_success: list[float] = []
        matched_task_success: list[float] = []
        matched_ids: list[str] = []

        for case in cases:
            success = case.get("success")
            if isinstance(success, bool):
                case_success.append(1.0 if success else 0.0)
            elif isinstance(success, (int, float)):
                case_success.append(float(success))
            for metric, value in (case.get("metrics") or {}).items():
                if isinstance(value, (int, float)):
                    all_metrics.setdefault(metric, []).append(float(value))

            rid = _case_request_id(case)
            e2e_row = e2e_by_request.get(rid) if rid else None
            if e2e_row is not None:
                matched_ids.append(rid)
                if isinstance(success, bool):
                    matched_success.append(1.0 if success else 0.0)
                ts = e2e_row.get("task_success")
                if isinstance(ts, bool):
                    matched_task_success.append(1.0 if ts else 0.0)
                elif isinstance(ts, (int, float)):
                    matched_task_success.append(float(ts))

        mean_metrics = {
            metric: _mean(values) for metric, values in all_metrics.items()
        }
        analysis["component_scores"][component] = {
            "n_cases": len(cases),
            "case_success_rate": _mean(case_success),
            "mean_metrics": mean_metrics,
        }

        n_matched = len(matched_ids)
        overlap_rate = n_matched / len(cases) if cases else 0.0
        entry: dict[str, Any] = {
            "n_component_cases": len(cases),
            "n_matched_requests": n_matched,
            "overlap_rate": round(overlap_rate, 4),
        }
        if n_matched >= MIN_PAIRS_FOR_CORRELATION and matched_success:
            r = _pearson(matched_success, matched_task_success)
            entry["correlation"] = {
                "status": "computed",
                "method": "pearson",
                "metric_pair": "component_case_success vs e2e_task_success",
                "pearson_r": r,
                "n_pairs": n_matched,
            }
        else:
            entry["correlation"] = {
                "status": "insufficient_overlap",
                "n_pairs": n_matched,
                "min_pairs_required": MIN_PAIRS_FOR_CORRELATION,
                "note": (
                    "Component cases and e2e requests share no request_id "
                    "(component benchmarks use synthetic case_ids). Correlation "
                    "requires running component benchmarks on the e2e request "
                    "set."
                ),
            }
        analysis["linking"][component] = entry

    analysis["analysis"] = {
        "summary": (
            "Component mean scores extracted per benchmark. Request-level "
            "correlation is computed only where component cases and e2e "
            "scored rows share request_id; current benchmarks use synthetic "
            "case_ids, so overlap is typically zero."
        ),
        "recommendation": (
            "To enable real component→e2e correlation, generate component "
            "benchmark cases from the same request set used by run_agent_eval "
            "and carry request_id into per_case_results."
        ),
    }

    # Save analysis
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    print(f"Link analysis saved to: {output_path}")
