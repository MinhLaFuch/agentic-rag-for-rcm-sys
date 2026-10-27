"""Tests for component benchmark regression analysis."""

from __future__ import annotations

import pytest

from package.evaluation.component._schema import BenchmarkSummary, BenchmarkResult
from package.evaluation.component._regression import compare_benchmarks, _compare_metrics, _compare_latency, _determine_summary


@pytest.fixture(autouse=True)
def ignore_deprecation_warnings():
    """Ignore datetime.utcnow deprecation warnings in tests."""
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning, message="datetime.datetime.utcnow")


def test_compare_metrics():
    """Test metric comparison logic."""
    baseline_metrics = {
        "success_rate_mean": 0.9,
        "error_rate_mean": 0.1,
        "latency_mean": 0.5,
    }
    current_metrics = {
        "success_rate_mean": 0.95,
        "error_rate_mean": 0.05,
        "latency_mean": 0.6,
    }

    changes = _compare_metrics(baseline_metrics, current_metrics, threshold=0.05)

    # Success rate increased (improvement)
    assert changes["success_rate"]["baseline"] == 0.9
    assert changes["success_rate"]["current"] == 0.95
    assert changes["success_rate"]["delta"] == pytest.approx(0.05)
    assert changes["success_rate"]["percent_change"] == pytest.approx(5.56, rel=0.01)
    assert changes["success_rate"]["significant"] is True

    # Error rate decreased (improvement)
    assert changes["error_rate"]["delta"] == -0.05
    assert changes["error_rate"]["percent_change"] == pytest.approx(-50.0, rel=0.01)
    assert changes["error_rate"]["significant"] is True


def test_compare_metrics_missing_current():
    """Test metric comparison when current metric is missing."""
    baseline_metrics = {"success_rate_mean": 0.9}
    current_metrics = {}

    changes = _compare_metrics(baseline_metrics, current_metrics, threshold=0.05)

    assert changes["success_rate"]["baseline"] == 0.9
    assert changes["success_rate"]["current"] is None
    assert changes["success_rate"]["delta"] is None
    assert changes["success_rate"]["significant"] is None


def test_compare_latency():
    """Test latency comparison logic."""
    baseline_latency = {
        "mean": 0.5,
        "p95": 1.0,
    }
    current_latency = {
        "mean": 0.6,
        "p95": 1.2,
    }

    changes = _compare_latency(baseline_latency, current_latency, threshold=0.1)

    # Mean latency increased by 20% (significant if threshold is 10%)
    assert changes["mean"]["baseline"] == 0.5
    assert changes["mean"]["current"] == 0.6
    assert changes["mean"]["delta"] == pytest.approx(0.1)
    assert changes["mean"]["percent_change"] == pytest.approx(20.0)
    assert changes["mean"]["significant"] is True


def test_compare_latency_decrease():
    """Test latency comparison when latency decreases (improvement)."""
    baseline_latency = {"mean": 1.0}
    current_latency = {"mean": 0.8}

    changes = _compare_latency(baseline_latency, current_latency, threshold=0.1)

    assert changes["mean"]["delta"] == pytest.approx(-0.2)
    assert changes["mean"]["percent_change"] == pytest.approx(-20.0)
    assert changes["mean"]["significant"] is True


def test_determine_summary_improved():
    """Test summary determination when metrics improved."""
    metric_changes = {
        "success_rate": {"delta": 0.1, "significant": True},
    }
    latency_changes = {
        "mean": {"delta": -0.1, "significant": True},
    }
    tag_changes = {}

    summary = _determine_summary(metric_changes, latency_changes, tag_changes)
    assert summary == "improved"


def test_determine_summary_regressed():
    """Test summary determination when metrics regressed."""
    metric_changes = {
        "success_rate": {"delta": -0.1, "significant": True},
    }
    latency_changes = {
        "mean": {"delta": 0.1, "significant": True},
    }
    tag_changes = {}

    summary = _determine_summary(metric_changes, latency_changes, tag_changes)
    assert summary == "regressed"


def test_determine_summary_neutral():
    """Test summary determination when no significant changes."""
    metric_changes = {
        "success_rate": {"delta": 0.01, "significant": False},
    }
    latency_changes = {
        "mean": {"delta": 0.01, "significant": False},
    }
    tag_changes = {}

    summary = _determine_summary(metric_changes, latency_changes, tag_changes)
    assert summary == "neutral"


def test_compare_benchmarks_full():
    """Test full benchmark comparison."""
    baseline = BenchmarkSummary(
        component="memory",
        metrics={"success_rate_mean": 0.9, "error_rate_mean": 0.1},
        latency={"mean": 0.5, "p95": 1.0},
        tags_summary={"normal": {"success_rate_mean": 0.9}},
    )
    current = BenchmarkSummary(
        component="memory",
        metrics={"success_rate_mean": 0.95, "error_rate_mean": 0.05},
        latency={"mean": 0.6, "p95": 1.2},
        tags_summary={"normal": {"success_rate_mean": 0.95}},
    )

    report = compare_benchmarks(baseline, current, metric_threshold=0.05, latency_threshold=0.1)

    assert report.baseline_summary == baseline
    assert report.current_summary == current
    assert "success_rate" in report.metric_changes
    assert "mean" in report.latency_changes
    assert "normal" in report.tag_changes
    assert report.summary in ["improved", "regressed", "neutral"]


def test_compare_benchmarks_roundtrip():
    """Test that RegressionReport can be serialized and deserialized."""
    import json

    baseline = BenchmarkSummary(
        component="memory",
        metrics={"success_rate_mean": 0.9},
        latency={"mean": 0.5},
    )
    current = BenchmarkSummary(
        component="memory",
        metrics={"success_rate_mean": 0.95},
        latency={"mean": 0.6},
    )

    report = compare_benchmarks(baseline, current)

    # Serialize
    report_dict = report.to_dict()
    report_json = json.dumps(report_dict)

    # Deserialize
    report_dict_loaded = json.loads(report_json)
    report_loaded = type(report).from_dict(report_dict_loaded)

    assert report_loaded.summary == report.summary
    assert report_loaded.baseline_summary.component == report.baseline_summary.component
    assert report_loaded.current_summary.component == report.current_summary.component
