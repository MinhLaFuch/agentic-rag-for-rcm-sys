"""Phase 1 regression tests: _run_all must not fake PASS and must exit non-zero on failure.

Covers package/evaluation/component/_run_all.py:
- missing success_rate -> None (not default 1.0)
- failed cases counted next to mean metrics
- not_implemented components counted as failed, shown with own status
- main() returns non-zero exit code when any component failed
"""

from __future__ import annotations

import json

import pytest

from package.evaluation.component import _run_all


def _write_result(path, *, success_rate=None, failed_cases=0, total_cases=3):
    per_case = [
        {"case_id": f"c{i}", "success": i >= failed_cases, "metrics": {"m": 1.0}, "latency_seconds": 0.01}
        for i in range(total_cases)
    ]
    metrics = {"m_mean": 1.0}
    if success_rate is not None:
        metrics["success_rate"] = success_rate
    path.write_text(json.dumps({
        "component": "x",
        "per_case_results": per_case,
        "metrics": metrics,
        "git_sha": "abc",
    }), encoding="utf-8")
    return str(path)


def _info(result_file=None, *, error=None, not_implemented=False):
    return {"result_file": result_file, "error": error, "not_implemented": not_implemented}


def test_missing_success_rate_is_none_not_pass(tmp_path):
    f = _write_result(tmp_path / "r.json", success_rate=None)
    agg = _run_all.aggregate_results({"comp": _info(f)})
    assert agg["components"]["comp"]["success_rate"] is None


def test_failed_cases_counted(tmp_path):
    f = _write_result(tmp_path / "r.json", success_rate=0.5, failed_cases=1, total_cases=2)
    agg = _run_all.aggregate_results({"comp": _info(f)})
    comp = agg["components"]["comp"]
    assert comp["cases_run"] == 2
    assert comp["failed_cases"] == 1
    assert comp["success_rate"] == 0.5


def test_not_implemented_counted_as_failed(tmp_path):
    agg = _run_all.aggregate_results({
        "executor": _info(None, error="NotImplementedError: ...", not_implemented=True),
        "memory": _info(_write_result(tmp_path / "m.json", success_rate=1.0)),
    })
    assert agg["components"]["executor"]["status"] == "not_implemented"
    assert agg["summary"]["failed_components"] == 1
    assert agg["summary"]["successful_components"] == 1


def test_main_returns_nonzero_on_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(_run_all, "run_all_benchmarks", lambda output_dir=None: {})
    monkeypatch.setattr(
        _run_all,
        "aggregate_results",
        lambda rf: {"timestamp": "t", "components": {}, "summary": {"total_components": 1, "successful_components": 0, "failed_components": 1}},
    )
    monkeypatch.setattr(_run_all, "generate_markdown_report", lambda a, p: None)
    monkeypatch.setattr(_run_all, "get_data_paths", lambda: _FakePaths(tmp_path))
    assert _run_all.main() == 1


class _FakePaths:
    def __init__(self, root):
        self._root = root

    def output_dir(self, key):
        d = self._root / key
        d.mkdir(parents=True, exist_ok=True)
        return d
