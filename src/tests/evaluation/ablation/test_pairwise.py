"""Tests cho pairwise_report: None-aware pairing, Wilson CI, McNemar, N/A kinds."""

from __future__ import annotations

import pytest

from package.evaluation.ablation import pairwise_report, render_pairwise_markdown, wilson_interval


def _row(rid: str, agent: str, kind: str, task_success, recall=0.5):
    return {
        "request_id": rid,
        "agent": agent,
        "kind": kind,
        "task_success": task_success,
        "recall@10": recall,
        "ndcg@10": recall,
        "mrr@10": recall,
    }


def _scored(agent: str, kind: str, n: int, success_pattern, none_ids=()):
    rows = []
    for i in range(n):
        rid = f"{kind}-{i}"
        ts = None if rid in none_ids else success_pattern(i)
        rows.append(_row(rid, agent, kind, ts, recall=0.5 + 0.01 * i))
    return rows


def test_binary_mcnemar_and_wilson():
    # A đúng 8/10, B đúng 10/10 -> b=0? thực tế A sai B đúng: c=2
    a = _scored("planner", "similar", 10, lambda i: i < 8)
    b = _scored("planner_memory", "similar", 10, lambda i: True)
    rep = pairwise_report(a, "planner", b, "planner_memory", confidence=0.95, bootstrap_resamples=100, seed=1)
    m = rep["kinds"]["similar"]["metrics"]["task_success"]
    assert m["n_effective"] == 10
    assert m["rate_a"] == 0.8 and m["rate_b"] == 1.0
    assert m["disagreement"]["n_a_wrong_b_correct"] == 2
    assert m["mcnemar"] is None or m["mcnemar"]["c"] == 2  # b+c=2 <10 -> None
    assert m["wilson_a"][0] < 0.8 < m["wilson_a"][1]


def test_none_pairs_dropped_and_counted():
    # planner personalized: tất cả None -> effective n = 0, không tính False
    a = _scored("planner", "personalized", 10, lambda i: True, none_ids={f"personalized-{i}" for i in range(10)})
    b = _scored("planner_memory", "personalized", 10, lambda i: i < 5)
    rep = pairwise_report(a, "planner", b, "planner_memory", confidence=0.95, bootstrap_resamples=100, seed=1)
    m = rep["kinds"]["personalized"]["metrics"]["task_success"]
    assert m["n_pairs_total"] == 10
    assert m["n_effective"] == 0
    assert m["n_dropped_none"] == 10
    assert "rate_a" not in m  # không bịa rate khi không có data


def test_partial_none_drops_only_those_pairs():
    a = _scored("planner", "similar", 10, lambda i: True, none_ids={"similar-3", "similar-7"})
    b = _scored("planner_memory", "similar", 10, lambda i: True)
    rep = pairwise_report(a, "planner", b, "planner_memory", confidence=0.95, bootstrap_resamples=100, seed=1)
    m = rep["kinds"]["similar"]["metrics"]["task_success"]
    assert m["n_effective"] == 8 and m["n_dropped_none"] == 2


def test_kind_only_on_one_side_is_not_applicable():
    # baseline không có ambiguous/unanswerable
    a = _scored("baseline", "similar", 10, lambda i: True)
    b = _scored("planner_memory", "similar", 10, lambda i: True) + _scored(
        "planner_memory", "unanswerable", 6, lambda i: False
    )
    rep = pairwise_report(a, "baseline", b, "planner_memory", confidence=0.95, bootstrap_resamples=100, seed=1)
    assert rep["kinds"]["unanswerable"]["not_applicable"] is True
    assert "không có cặp" in rep["kinds"]["unanswerable"]["reason"]
    assert "unanswerable" not in [k for k in rep["kinds"] if not rep["kinds"][k].get("not_applicable")]


def test_continuous_metric_bootstrap_ci():
    a = _scored("x", "similar", 10, lambda i: True)
    b = _scored("y", "similar", 10, lambda i: True)
    # làm B recall cao hơn A một chút
    for r in b:
        r["recall@10"] += 0.1
    rep = pairwise_report(a, "x", b, "y", confidence=0.95, bootstrap_resamples=200, seed=7)
    m = rep["kinds"]["similar"]["metrics"]["recall@10"]
    assert m["type"] == "continuous"
    assert m["diff"] == pytest.approx(0.1)
    assert m["ci_lower"] <= m["diff"] <= m["ci_upper"]


def test_wilson_interval_bounds():
    lo, hi = wilson_interval(8, 10, 0.95)
    assert 0 < lo < 0.8 < hi < 1
    assert wilson_interval(0, 0) is None


def test_render_markdown_contains_kind_rows():
    a = _scored("planner", "similar", 10, lambda i: i < 8)
    b = _scored("planner_memory", "similar", 10, lambda i: True)
    rep = pairwise_report(a, "planner", b, "planner_memory", confidence=0.95, bootstrap_resamples=100, seed=1)
    md = render_pairwise_markdown(rep, title="t")
    assert "| similar | task_success |" in md
    assert "recall@10" in md
