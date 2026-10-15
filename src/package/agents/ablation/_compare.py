"""Logic so sánh giữa hai agent/groups."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from package.agents.evaluation._schema import ORACLE_KINDS
from ._loader import check_compatibility, load_group_data
from ._limits import get_ablation_limits
from ._statistics import bootstrap_ci, mcnemar_test


def pair_by_request_id(
    scored_a: list[dict[str, Any]],
    scored_b: list[dict[str, Any]],
    agent_a: str,
    agent_b: str,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Ghép cặp scored data theo request_id."""
    a_by_id = {r["request_id"]: r for r in scored_a if r["agent"] == agent_a}
    b_by_id = {r["request_id"]: r for r in scored_b if r["agent"] == agent_b}
    
    pairs = []
    for request_id in a_by_id:
        if request_id in b_by_id:
            pairs.append((a_by_id[request_id], b_by_id[request_id]))
    
    return pairs


def average_across_runs(
    scored_list: list[list[dict[str, Any]]],
    agent: str,
) -> dict[str, dict[str, Any]]:
    """
    Trung bình theo request_id trên nhiều lần chạy.
    
    Trả về dict: request_id -> averaged scored record
    """
    if not scored_list:
        return {}
    
    # Gom tất cả records theo request_id
    by_id = defaultdict(list)
    for scored in scored_list:
        for r in scored:
            if r["agent"] == agent:
                by_id[r["request_id"]].append(r)
    
    # Trung bình các metric số
    averaged = {}
    for request_id, records in by_id.items():
        if not records:
            continue
        
        # Lấy record đầu tiên làm template
        base = records[0].copy()
        
        # Trung bình các metric số
        numeric_keys = [
            "recall@10", "ndcg@10", "mrr@10", "hit_rate@10",
            "llm_latency_seconds", "tool_latency_seconds", "wall_seconds",
            "prompt_tokens", "completion_tokens",
        ]
        
        for key in numeric_keys:
            if key in base and base[key] is not None:
                values = [r[key] for r in records if r[key] is not None]
                if values:
                    base[key] = sum(values) / len(values)
        
        # Các metric nhị phân: giữ nguyên (không trung bình)
        # task_success, first_attempt_ok, tool_selection_ok, asked_clarification
        
        averaged[request_id] = base
    
    return averaged


def compute_metric_diff(
    pairs: list[tuple[dict[str, Any], dict[str, Any]]],
    metric: str,
    k: int,
    limits: Any,
) -> dict[str, Any]:
    """
    Tính hiệu, khoảng tin cậy bootstrap cho một metric.
    
    Trả về dict với:
    - mean_a, mean_b: trung bình A và B
    - diff: B - A
    - ci_lower, ci_upper: khoảng tin cậy của diff
    - n: số cặp
    """
    if not pairs:
        return {"n": 0}
    
    # Format metric name with k if needed
    metric_formatted = metric.format(k=k) if "{k}" in metric else metric
    
    values_a = []
    values_b = []
    
    for a, b in pairs:
        val_a = a.get(metric_formatted)
        val_b = b.get(metric_formatted)
        
        if val_a is not None and val_b is not None:
            values_a.append(float(val_a))
            values_b.append(float(val_b))
    
    if not values_a:
        return {"n": 0}
    
    n = len(values_a)
    mean_a = sum(values_a) / n
    mean_b = sum(values_b) / n
    diff = mean_b - mean_a
    
    # Bootstrap CI trên diff
    diffs = [values_b[i] - values_a[i] for i in range(n)]
    ci_lower, ci_upper = bootstrap_ci(diffs, limits.bootstrap_resamples, limits.confidence, limits.seed)
    
    return {
        "mean_a": mean_a,
        "mean_b": mean_b,
        "diff": diff,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "n": n,
    }


def compute_binary_disagreement(
    pairs: list[tuple[dict[str, Any], dict[str, Any]]],
    metric: str,
) -> dict[str, int]:
    """
    Đếm số cặp không nhất quán cho metric nhị phân.
    
    Trả về dict với:
    - n_correct_both: A đúng, B đúng
    - n_a_correct_b_wrong: A đúng, B sai
    - n_a_wrong_b_correct: A sai, B đúng
    - n_both_wrong: A sai, B sai
    """
    counts = {
        "n_correct_both": 0,
        "n_a_correct_b_wrong": 0,
        "n_a_wrong_b_correct": 0,
        "n_both_wrong": 0,
    }
    
    for a, b in pairs:
        val_a = a.get(metric, False)
        val_b = b.get(metric, False)
        
        if val_a and val_b:
            counts["n_correct_both"] += 1
        elif val_a and not val_b:
            counts["n_a_correct_b_wrong"] += 1
        elif not val_a and val_b:
            counts["n_a_wrong_b_correct"] += 1
        else:
            counts["n_both_wrong"] += 1
    
    return counts


def compare_two_groups(
    group_a: dict[str, Any],
    group_b: dict[str, Any],
    agent_a: str,
    agent_b: str,
    kinds: list[str] | None,
    k: int,
    limits: Any,
) -> dict[str, Any]:
    """
    So sánh hai groups cho một agent.
    
    Trả về dict với kết quả so sánh cho từng kind × segment × metric.
    """
    # Kiểm tra compatibility giữa configs
    configs_a = group_a["configs"]
    configs_b = group_b["configs"]
    
    # Chỉ cần kiểm tra config đầu tiên của mỗi group (giả định cùng cấu hình)
    compatible, reason = check_compatibility(configs_a[0], configs_b[0])
    if not compatible:
        return {"error": reason}
    
    # Nếu group có nhiều lần chạy, trung bình trước
    if len(group_a["scored"]) > 1:
        scored_a_avg = average_across_runs(group_a["scored"], agent_a)
        scored_a_list = [list(scored_a_avg.values())]
    else:
        scored_a_list = group_a["scored"]
    
    if len(group_b["scored"]) > 1:
        scored_b_avg = average_across_runs(group_b["scored"], agent_b)
        scored_b_list = [list(scored_b_avg.values())]
    else:
        scored_b_list = group_b["scored"]
    
    # Flatten scored data
    scored_a_flat = [r for scored in scored_a_list for r in scored]
    scored_b_flat = [r for scored in scored_b_list for r in scored]
    
    # Ghép cặp theo request_id
    pairs = pair_by_request_id(scored_a_flat, scored_b_flat, agent_a, agent_b)
    
    if not pairs:
        return {"error": f"No paired requests found for {agent_a} vs {agent_b}"}
    
    # Group by kind and segment
    by_kind_segment = defaultdict(list)
    for a, b in pairs:
        kind = a.get("kind", "unknown")
        segment = a.get("segment", "unknown")
        
        if kinds is None or kind in kinds:
            by_kind_segment[(kind, segment)].append((a, b))
    
    # Compute metrics for each kind × segment
    results = {}
    for (kind, segment), kind_pairs in by_kind_segment.items():
        kind_key = f"{kind}/{segment}"
        results[kind_key] = {}
        
        for metric in limits.metrics:
            metric_formatted = metric.format(k=k) if "{k}" in metric else metric
            
            # Kiểm tra metric có trong data
            if not kind_pairs or metric_formatted not in kind_pairs[0][0]:
                results[kind_key][metric_formatted] = {"n": 0, "missing": True}
                continue
            
            # Compute diff
            diff_result = compute_metric_diff(kind_pairs, metric, k, limits)
            results[kind_key][metric_formatted] = diff_result
            
            # Nếu metric nhị phân, thêm McNemar
            if metric in ["task_success", "first_attempt_ok", "tool_selection_ok", "asked_clarification"]:
                disagreement = compute_binary_disagreement(kind_pairs, metric)
                mcnemar = mcnemar_test(
                    disagreement["n_correct_both"],
                    disagreement["n_a_correct_b_wrong"],
                    disagreement["n_a_wrong_b_correct"],
                    disagreement["n_both_wrong"],
                )
                if mcnemar:
                    results[king_key][metric_formatted]["mcnemar"] = {
                        "b": mcnemar[0],
                        "c": mcnemar[1],
                        "p": mcnemar[2],
                    }
    
    # Aggregate by kind (across segments)
    by_kind = defaultdict(list)
    for (kind, segment), kind_pairs in by_kind_segment.items():
        if kinds is None or kind in kinds:
            by_kind[kind].extend(kind_pairs)
    
    results["all_kinds"] = {}
    for kind, kind_pairs in by_kind.items():
        results["all_kinds"][kind] = {}
        
        for metric in limits.metrics:
            metric_formatted = metric.format(k=k) if "{k}" in metric else metric
            
            if not kind_pairs or metric_formatted not in kind_pairs[0][0]:
                results["all_kinds"][kind][metric_formatted] = {"n": 0, "missing": True}
                continue
            
            diff_result = compute_metric_diff(kind_pairs, metric, k, limits)
            results["all_kinds"][kind][metric_formatted] = diff_result
            
            if metric in ["task_success", "first_attempt_ok", "tool_selection_ok", "asked_clarification"]:
                disagreement = compute_binary_disagreement(kind_pairs, metric)
                mcnemar = mcnemar_test(
                    disagreement["n_correct_both"],
                    disagreement["n_a_correct_b_wrong"],
                    disagreement["n_a_wrong_b_correct"],
                    disagreement["n_both_wrong"],
                )
                if mcnemar:
                    results["all_kinds"][kind][metric_formatted]["mcnemar"] = {
                        "b": mcnemar[0],
                        "c": mcnemar[1],
                        "p": mcnemar[2],
                    }
    
    # Compute variance across runs if multiple runs
    variance_info = {}
    if len(group_a["scored"]) > 1:
        variance_info["group_a_runs"] = len(group_a["scored"])
        # Could compute std across runs here
    
    if len(group_b["scored"]) > 1:
        variance_info["group_b_runs"] = len(group_b["scored"])
    
    if not variance_info:
        variance_info["note"] = "Only 1 run per group, cannot compute variance"
    
    results["variance"] = variance_info
    results["n_pairs"] = len(pairs)
    
    return results


def find_disagreements(
    pairs: list[tuple[dict[str, Any], dict[str, Any]]],
    metric: str = "task_success",
) -> list[dict[str, Any]]:
    """
    Tìm các request mà hai agent khác nhau về metric.
    
    Trả về list dict với request_id, text, kind, segment, và tóm tắt trajectory.
    """
    disagreements = []
    
    for a, b in pairs:
        val_a = a.get(metric, False)
        val_b = b.get(metric, False)
        
        if val_a != val_b:
            disagreements.append({
                "request_id": a.get("request_id"),
                "text": a.get("text", ""),
                "kind": a.get("kind"),
                "segment": a.get("segment"),
                "a_trajectory": {
                    "plan": a.get("plan", [])[:5],  # rút gọn
                    "steps": [{"tool": s.get("tool"), "ok": s.get("ok")} for s in (a.get("steps") or [])[:5]],
                    "reflections": a.get("reflections", 0),
                },
                "b_trajectory": {
                    "plan": b.get("plan", [])[:5],
                    "steps": [{"tool": s.get("tool"), "ok": s.get("ok")} for s in (b.get("steps") or [])[:5]],
                    "reflections": b.get("reflections", 0),
                },
            })
    
    return disagreements
