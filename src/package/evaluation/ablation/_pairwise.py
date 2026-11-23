"""Pairwise ablation analysis trên scored.jsonl — None-aware.

Khác compare_two_groups (coi None như False trong McNemar), ở đây mọi cặp có
giá trị None ở một phía đều bị LOẠI khỏi effective n và được báo cáo minh bạch.
Dùng cho các contrast mà metric có thể undefined (vd planner không memory
trả task_success=None cho personalized).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ._statistics import bootstrap_ci, mcnemar_test, wilson_interval

BINARY_METRICS = ("task_success", "first_attempt_ok", "tool_selection_ok")
CONTINUOUS_METRICS = ("recall@10", "ndcg@10", "mrr@10")


def _by_request(scored: list[dict[str, Any]], agent: str) -> dict[str, dict[str, Any]]:
    return {r["request_id"]: r for r in scored if r.get("agent") == agent}


def _kind_of(record: dict[str, Any]) -> str:
    return str(record.get("kind") or "unknown")


def pairwise_report(
    scored_a: list[dict[str, Any]],
    agent_a: str,
    scored_b: list[dict[str, Any]],
    agent_b: str,
    *,
    kinds: list[str] | None = None,
    binary_metrics: tuple[str, ...] = BINARY_METRICS,
    continuous_metrics: tuple[str, ...] = CONTINUOUS_METRICS,
    confidence: float = 0.95,
    bootstrap_resamples: int = 10000,
    seed: int = 42,
) -> dict[str, Any]:
    """So sánh A vs B theo request_id, theo kind. Trả report dict.

    Mỗi kind gồm:
    - n_requests_a / n_requests_b: số request mỗi phía (trước pairing)
    - n_pairs: cặp request_id có mặt ở cả hai phía
    - not_applicable: kind chỉ có ở một phía (vd baseline không có
      ambiguous/unanswerable) -> không so được
    - per metric: effective n sau khi loại cặp None, mean_a/mean_b,
      Wilson CI cho metric nhị phân, McNemar (b, c, p) cho nhị phân,
      bootstrap CI của mean diff cho metric liên tục.
    """
    a_by_id = _by_request(scored_a, agent_a)
    b_by_id = _by_request(scored_b, agent_b)

    kinds_a = {_kind_of(r) for r in a_by_id.values()}
    kinds_b = {_kind_of(r) for r in b_by_id.values()}
    all_kinds = sorted((kinds_a | kinds_b) - ({"unknown"} if not (kinds_a | kinds_b) else set()))
    if kinds is not None:
        all_kinds = [k for k in all_kinds if k in set(kinds)]

    report: dict[str, Any] = {
        "agent_a": agent_a,
        "agent_b": agent_b,
        "n_requests_a": len(a_by_id),
        "n_requests_b": len(b_by_id),
        "confidence": confidence,
        "kinds": {},
    }

    for kind in all_kinds:
        pairs = [
            (a_by_id[rid], b_by_id[rid])
            for rid in a_by_id.keys() & b_by_id.keys()
            if _kind_of(a_by_id[rid]) == kind and _kind_of(b_by_id[rid]) == kind
        ]

        entry: dict[str, Any] = {
            "n_requests_a": sum(1 for r in a_by_id.values() if _kind_of(r) == kind),
            "n_requests_b": sum(1 for r in b_by_id.values() if _kind_of(r) == kind),
            "n_pairs": len(pairs),
            "metrics": {},
        }

        only_a = entry["n_requests_a"] > 0 and entry["n_requests_b"] == 0
        only_b = entry["n_requests_b"] > 0 and entry["n_requests_a"] == 0
        if only_a or only_b or entry["n_pairs"] == 0:
            entry["not_applicable"] = True
            entry["reason"] = (
                f"kind '{kind}' chỉ có ở {'A' if only_a else 'B' if only_b else 'một phía'}; "
                "không có cặp request_id chung để so sánh"
            )
            report["kinds"][kind] = entry
            continue

        for metric in binary_metrics:
            vals = [(a.get(metric), b.get(metric)) for a, b in pairs]
            usable = [(va, vb) for va, vb in vals if va is not None and vb is not None]
            n_eff = len(usable)
            m: dict[str, Any] = {
                "type": "binary",
                "n_pairs_total": len(pairs),
                "n_effective": n_eff,
                "n_dropped_none": len(pairs) - n_eff,
            }
            if n_eff:
                sa = sum(1 for va, _ in usable if va)
                sb = sum(1 for _, vb in usable if vb)
                m["mean_a"] = sa / n_eff
                m["mean_b"] = sb / n_eff
                wa = wilson_interval(sa, n_eff, confidence)
                wb = wilson_interval(sb, n_eff, confidence)
                m["rate_a"], m["rate_b"] = m["mean_a"], m["mean_b"]
                m["wilson_a"] = list(wa) if wa else None
                m["wilson_b"] = list(wb) if wb else None
                disc = {
                    "n_correct_both": sum(1 for va, vb in usable if va and vb),
                    "n_a_correct_b_wrong": sum(1 for va, vb in usable if va and not vb),
                    "n_a_wrong_b_correct": sum(1 for va, vb in usable if not va and vb),
                    "n_both_wrong": sum(1 for va, vb in usable if not va and not vb),
                }
                m["disagreement"] = disc
                mc = mcnemar_test(
                    disc["n_correct_both"],
                    disc["n_a_correct_b_wrong"],
                    disc["n_a_wrong_b_correct"],
                    disc["n_both_wrong"],
                )
                m["mcnemar"] = {"b": mc[0], "c": mc[1], "p": mc[2]} if mc else None
            entry["metrics"][metric] = m

        for metric in continuous_metrics:
            usable = [
                (float(a[metric]), float(b[metric]))
                for a, b in pairs
                if a.get(metric) is not None and b.get(metric) is not None
            ]
            n_eff = len(usable)
            m = {
                "type": "continuous",
                "n_pairs_total": len(pairs),
                "n_effective": n_eff,
                "n_dropped_none": len(pairs) - n_eff,
            }
            if n_eff:
                diffs = [vb - va for va, vb in usable]
                lo, hi = bootstrap_ci(diffs, bootstrap_resamples, confidence, seed)
                m["mean_a"] = sum(v for v, _ in usable) / n_eff
                m["mean_b"] = sum(v for _, v in usable) / n_eff
                m["diff"] = m["mean_b"] - m["mean_a"]
                m["ci_lower"], m["ci_upper"] = lo, hi
            entry["metrics"][metric] = m

        report["kinds"][kind] = entry

    return report


def render_pairwise_markdown(report: dict[str, Any], title: str = "Pairwise ablation") -> str:
    """Render report dict thành markdown ngắn gọn."""
    lines = [
        f"# {title}",
        "",
        f"- A: `{report['agent_a']}` ({report['n_requests_a']} requests)",
        f"- B: `{report['agent_b']}` ({report['n_requests_b']} requests)",
        f"- confidence: {report['confidence']}",
        "",
        "| kind | metric | n_eff | A | B | diff / McNemar |",
        "|---|---|---|---|---|---|",
    ]
    for kind, entry in report["kinds"].items():
        if entry.get("not_applicable"):
            lines.append(f"| {kind} | — | 0 | — | — | not applicable ({entry['reason']}) |")
            continue
        for metric, m in entry["metrics"].items():
            if m["n_effective"] == 0:
                lines.append(f"| {kind} | {metric} | 0 | — | — | all pairs dropped (None) |")
                continue
            if m["type"] == "binary":
                mc = m.get("mcnemar")
                mc_txt = f"McNemar b={mc['b']:.0f} c={mc['c']:.0f} p={mc['p']}" if mc else "McNemar n/a (b+c<10)"
                extra = f" (drop {m['n_dropped_none']} None)" if m["n_dropped_none"] else ""
                lines.append(
                    f"| {kind} | {metric} | {m['n_effective']}{extra} | "
                    f"{m['rate_a']:.3f} [{m['wilson_a'][0]:.3f},{m['wilson_a'][1]:.3f}] | "
                    f"{m['rate_b']:.3f} [{m['wilson_b'][0]:.3f},{m['wilson_b'][1]:.3f}] | {mc_txt} |"
                )
            else:
                lines.append(
                    f"| {kind} | {metric} | {m['n_effective']} | {m['mean_a']:.4f} | "
                    f"{m['mean_b']:.4f} | diff={m['diff']:+.4f} CI[{m['ci_lower']:+.4f},{m['ci_upper']:+.4f}] |"
                )
    return "\n".join(lines) + "\n"
