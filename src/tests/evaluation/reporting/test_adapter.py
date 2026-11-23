"""Tests for reporting._adapter.build_report_results."""

import json

from package.evaluation.reporting import (
    build_report_results,
    generate_all_charts,
    generate_csv_export,
    generate_failure_report,
    generate_markdown_report,
)


def _row(agent="planner", kind="constrained", request_id="r1", **kw):
    base = {
        "agent": agent,
        "kind": kind,
        "request_id": request_id,
        "task_success": 1.0,
        "precision@10": 0.5,
        "wall_seconds": 1.0,
        "provider_error": False,
        "candidate_generation_count": 100,
        "retrieved_count": 50,
        "filtered_count": 20,
        "ranked_count": 10,
        "n_recommended": 5,
        "stage_lost": None,
    }
    base.update(kw)
    return base


def test_request_kinds_keyed_by_agent_and_kind_with_real_stats():
    rows = [
        _row(agent="planner", kind="constrained", task_success=1.0, **{"precision@10": 0.6}),
        _row(agent="planner", kind="constrained", task_success=0.0, **{"precision@10": 0.2},
             request_id="r2"),
        _row(agent="baseline", kind="constrained", task_success=1.0, **{"precision@10": 0.9},
             request_id="r3"),
    ]
    res = build_report_results(rows, [], k=10)
    kinds = {k["kind"]: k["metrics"] for k in res["request_kinds"]}
    # agent dimension preserved: two distinct entries, not merged by kind
    assert set(kinds) == {"baseline/constrained", "planner/constrained"}
    planner = kinds["planner/constrained"]
    assert planner["task_success"]["mean"] == 0.5
    assert planner["task_success"]["min"] == 0.0
    assert planner["task_success"]["max"] == 1.0
    assert planner["task_success"]["count"] == 2


def test_none_values_excluded_not_zeroed():
    rows = [
        _row(task_success=1.0),
        _row(task_success=None, request_id="r2"),
        _row(task_success=0.0, request_id="r3"),
    ]
    res = build_report_results(rows, [], k=10)
    metrics = res["request_kinds"][0]["metrics"]
    # None row dropped from count; mean over {1.0, 0.0} only
    assert metrics["task_success"]["count"] == 2
    assert metrics["task_success"]["mean"] == 0.5
    pooled = res["metric_values"]["task_success"]
    assert pooled == [1.0, 0.0]


def test_summary_and_latency_and_funnel():
    rows = [
        _row(wall_seconds=2.0, candidate_generation_count=None),
        _row(wall_seconds=4.0, request_id="r2", n_recommended=None),
    ]
    res = build_report_results(rows, [], k=10)
    assert res["summary"]["scored_rows"] == 2
    assert res["summary"]["requests"] == 2
    assert res["summary"]["k"] == 10
    assert res["latency_values"] == [2.0, 4.0]
    funnel = res["retrieval_funnel"]
    # candidate_generation_count: one None excluded -> mean of single value
    assert funnel["candidate_generation_count"] == 100.0
    # n_recommended: one None excluded -> mean of single value
    assert funnel["n_recommended"] == 5.0


def test_failures_carry_stage_and_trajectory_error():
    rows = [
        _row(task_success=0.0, stage_lost="retrieve", request_id="r1"),
        _row(task_success=1.0, request_id="r2"),  # not a failure
        _row(task_success=None, provider_error=True, request_id="r3"),
    ]
    trajs = [
        {"request_id": "r1", "agent": "planner", "error": "ValueError: bad plan"},
        {"request_id": "r3", "agent": "planner", "error": None},
    ]
    res = build_report_results(rows, trajs, k=10, trajectory_path="trajectories.jsonl")
    failures = res["failures"]
    assert len(failures) == 2
    f1 = next(f for f in failures if f["case_id"] == "planner:r1")
    assert f1["failure_stage"] == "retrieve"
    assert f1["error"] == "ValueError: bad plan"
    assert f1["trace_file"] == "trajectories.jsonl"
    f3 = next(f for f in failures if f["case_id"] == "planner:r3")
    assert f3["failure_stage"] == "unknown"  # stage_lost missing -> unknown, not fabricated
    assert f3["error"] == "provider_error" or f3["error"]  # falls back to answer_status/task_success


def test_multi_turn_passthrough_and_absent_sections():
    res = build_report_results([_row()], [], k=10,
                               multi_turn={"turn_success_rate": 0.9})
    assert res["multi_turn"] == {"turn_success_rate": 0.9}
    # layers/components never fabricated
    assert "layers" not in res
    assert "components" not in res


def test_generators_accept_adapter_output(tmp_path):
    """End-to-end: adapter results render through all generators without error."""
    rows = [
        _row(task_success=1.0, **{"precision@10": 0.5}),
        _row(task_success=0.0, stage_lost="rank_topk", request_id="r2",
             **{"precision@10": 0.1}, wall_seconds=3.0),
    ]
    trajs = [{"request_id": "r2", "agent": "planner", "error": "timeout"}]
    res = build_report_results(rows, trajs, k=10, trajectory_path="t.jsonl",
                               multi_turn={"turn_success_rate": 0.5,
                                           "conversation_success_rate": 0.4,
                                           "context_retention": 0.7})
    md = tmp_path / "report.md"
    generate_markdown_report(res, md)
    assert "Agent Evaluation Report" in md.read_text(encoding="utf-8")
    assert "planner/constrained" in md.read_text(encoding="utf-8")
    generate_csv_export(res, tmp_path / "report.csv")
    assert (tmp_path / "report.csv").exists()
    generate_failure_report(res["failures"], tmp_path / "failures.md")
    assert "rank_topk" in (tmp_path / "failures.md").read_text(encoding="utf-8")
    charts = generate_all_charts(res, tmp_path / "charts")
    # request-kind heatmap + latency + funnel + multi-turn charts render
    assert charts["request_kind_heatmap"].exists()
    assert charts["latency_distribution"].exists()
    assert charts["retrieval_funnel"].exists()
    assert charts["multi_turn_performance"].exists()
    # no layer data -> layer chart not emitted (section absent by design)
    assert "layer_comparison" not in charts
