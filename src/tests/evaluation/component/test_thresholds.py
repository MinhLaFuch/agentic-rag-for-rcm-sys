"""Regression tests for the component quality gate (thresholds, Phase 2.1).

Rules under test:
- success=True only means "ran without exception"; `passed` is the quality gate.
- A component/metric without thresholds is "not_evaluated" (None), never an
  implicit PASS.
- A thresholded metric missing from the aggregated metrics → cannot evaluate.
"""

from __future__ import annotations

import json

import pytest

from package.evaluation.component._evaluator import ComponentEvaluator, evaluate_thresholds
from package.evaluation.component._schema import BenchmarkCase
from package.evaluation.component._run_all import aggregate_results


def test_no_thresholds_returns_none():
    assert evaluate_thresholds({"x_mean": 1.0}, None) is None
    assert evaluate_thresholds({"x_mean": 1.0}, {}) is None
    assert evaluate_thresholds({"x_mean": 1.0}, {"min": {}, "max": {}}) is None


def test_all_checks_pass():
    result = evaluate_thresholds(
        {"acc_mean": 0.97, "success_rate": 1.0, "leak_max": 0.0},
        {"min": {"acc_mean": 0.95, "success_rate": 1.0}, "max": {"leak_max": 0.0}},
    )
    assert result["passed"] is True
    assert all(v == "pass" for v in result["checks"].values())


def test_failing_check_marks_failed():
    result = evaluate_thresholds(
        {"acc_mean": 0.80, "success_rate": 1.0},
        {"min": {"acc_mean": 0.95, "success_rate": 1.0}},
    )
    assert result["passed"] is False
    assert result["checks"]["min:acc_mean"] == "fail"
    assert result["checks"]["min:success_rate"] == "pass"


def test_missing_thresholded_metric_cannot_evaluate():
    result = evaluate_thresholds(
        {"acc_mean": 0.99},
        {"min": {"acc_mean": 0.95, "no_such_metric_mean": 0.5}},
    )
    assert result["passed"] is None
    assert result["checks"]["min:no_such_metric_mean"] == "missing"


def test_max_bound_is_inclusive():
    assert evaluate_thresholds({"leak_max": 0.0}, {"max": {"leak_max": 0.0}})["passed"] is True
    assert evaluate_thresholds({"leak_max": 0.1}, {"max": {"leak_max": 0.0}})["passed"] is False


class _FakeEvaluator(ComponentEvaluator):
    """Returns a fixed metric value so thresholds can be exercised without a real component."""

    def __init__(self, metric_value: float, config=None):
        super().__init__(config)
        self._metric_value = metric_value

    def run_component(self, case_input):
        return {"ok": True}

    def score_component(self, actual_output, expected):
        return {"quality": self._metric_value}


def _case() -> BenchmarkCase:
    return BenchmarkCase(case_id="c1", input={}, expected={}, tags=[], metadata={})


def test_run_benchmark_records_thresholds_result():
    thresholds = {"min": {"quality_mean": 0.9}}
    evaluator = _FakeEvaluator(0.95, config={"thresholds": thresholds})
    summary = evaluator.run_benchmark([_case()], component_name="fake")
    assert summary.thresholds_result["passed"] is True
    # Round-trips through JSON (what _run_all consumes).
    assert json.loads(summary.to_json())["thresholds_result"]["passed"] is True


def test_run_benchmark_low_metric_fails_gate_but_case_still_success():
    evaluator = _FakeEvaluator(0.5, config={"thresholds": {"min": {"quality_mean": 0.9}}})
    summary = evaluator.run_benchmark([_case()], component_name="fake")
    assert summary.per_case_results[0].success is True  # ran fine
    assert summary.thresholds_result["passed"] is False  # but below threshold


def test_run_benchmark_without_thresholds_is_not_evaluated():
    evaluator = _FakeEvaluator(0.5, config={})
    summary = evaluator.run_benchmark([_case()], component_name="fake")
    assert summary.thresholds_result is None


def _result_file(tmp_path, thresholds_result):
    payload = {
        "component": "fake",
        "per_case_results": [{"case_id": "c1", "success": True, "metrics": {}, "latency_seconds": 0.01}],
        "metrics": {"success_rate": 1.0},
        "thresholds_result": thresholds_result,
    }
    path = tmp_path / "fake_benchmark.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return {"fake": {"result_file": str(path), "error": None, "not_implemented": False}}


def test_aggregate_maps_gate_labels(tmp_path):
    agg = aggregate_results(_result_file(tmp_path, {"passed": True, "checks": {"min:x": "pass"}}))
    assert agg["components"]["fake"]["quality_gate"] == "pass"

    agg = aggregate_results(_result_file(tmp_path, {"passed": False, "checks": {"min:x": "fail"}}))
    assert agg["components"]["fake"]["quality_gate"] == "fail"

    agg = aggregate_results(_result_file(tmp_path, None))
    assert agg["components"]["fake"]["quality_gate"] == "not_evaluated"


def test_aggregate_missing_thresholds_result_is_not_evaluated(tmp_path):
    path = tmp_path / "old_benchmark.json"
    path.write_text(json.dumps({
        "per_case_results": [{"case_id": "c1", "success": True, "metrics": {}, "latency_seconds": 0.01}],
        "metrics": {"success_rate": 1.0},
    }), encoding="utf-8")
    agg = aggregate_results({"fake": {"result_file": str(path), "error": None, "not_implemented": False}})
    assert agg["components"]["fake"]["quality_gate"] == "not_evaluated"
