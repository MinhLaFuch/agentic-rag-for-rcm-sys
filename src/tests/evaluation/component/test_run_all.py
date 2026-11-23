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


def _write_multi_turn_result(path):
    path.write_text(json.dumps({
        "multi_turn_version": "1.0",
        "total_conversations": 11,
        "turn_success_rate": 0.8,
        "conversation_success_rate": 0.5,
        "metrics": {"tool_call_match_rate": 0.6},
        "latency": {"mean": 1.2, "p95": 3.0},
        "git_sha": "abc",
    }), encoding="utf-8")
    return str(path)


def test_skipped_no_credentials_is_visible_not_failed(tmp_path):
    agg = _run_all.aggregate_results({
        "multi_turn": {"result_file": None, "error": "no LLM", "not_implemented": False,
                       "status": "skipped_no_credentials"},
        "memory": _info(_write_result(tmp_path / "m.json", success_rate=1.0)),
    })
    mt = agg["components"]["multi_turn"]
    assert mt["status"] == "skipped_no_credentials"
    assert mt["quality_gate"] == "not_evaluated"
    assert agg["summary"]["skipped_components"] == 1
    assert agg["summary"]["failed_components"] == 0
    assert agg["summary"]["successful_components"] == 1


def test_multi_turn_result_maps_conversation_summary(tmp_path):
    f = _write_multi_turn_result(tmp_path / "mt.json")
    agg = _run_all.aggregate_results({"multi_turn": _info(f)})
    mt = agg["components"]["multi_turn"]
    assert mt["status"] == "success"
    assert mt["cases_run"] == 11
    assert mt["metrics"]["turn_success_rate"] == 0.8
    assert mt["metrics"]["conversation_success_rate"] == 0.5
    assert mt["metrics"]["tool_call_match_rate"] == 0.6
    assert mt["latency"]["mean"] == 1.2
    assert mt["success_rate"] is None
    assert agg["summary"]["successful_components"] == 1


def test_run_multi_turn_skips_without_llm(monkeypatch):
    monkeypatch.setattr(_run_all, "_llm_configured", lambda: False)
    info = _run_all._run_multi_turn()
    assert info["status"] == "skipped_no_credentials"
    assert info["result_file"] is None


def test_run_multi_turn_runs_cli_and_parses_result(monkeypatch, tmp_path):
    monkeypatch.setattr(_run_all, "_llm_configured", lambda: True)
    monkeypatch.setattr(_run_all, "get_data_paths", lambda: _FakePaths(tmp_path))
    monkeypatch.setattr(
        _run_all.subprocess, "run",
        lambda *a, **k: type("R", (), {"returncode": 0, "stdout": "Results saved to: out/mt.json\n", "stderr": ""})(),
    )
    info = _run_all._run_multi_turn()
    assert info["status"] == "success"
    assert info["result_file"].endswith(("out/mt.json", "out\\mt.json"))


def test_run_multi_turn_failed_exit_is_failed(monkeypatch, tmp_path):
    monkeypatch.setattr(_run_all, "_llm_configured", lambda: True)
    monkeypatch.setattr(_run_all, "get_data_paths", lambda: _FakePaths(tmp_path))
    monkeypatch.setattr(
        _run_all.subprocess, "run",
        lambda *a, **k: type("R", (), {"returncode": 2, "stdout": "", "stderr": "boom"})(),
    )
    info = _run_all._run_multi_turn()
    assert info["status"] == "failed"
    assert info["error"] == "boom"


def test_jev_configured_env_fallback(monkeypatch):
    for var in ("JEV_API_KEY", "TYPESAFE_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(
        "package.config.load_config",
        lambda *a, **k: {"api_key": ""},
    )
    assert _run_all._jev_configured() is False
    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    assert _run_all._jev_configured() is True


def test_grounding_skipped_without_jev(monkeypatch, tmp_path):
    """run_all_benchmarks: grounding không có Jev credential -> skipped, không subprocess."""
    monkeypatch.setattr(_run_all, "_jev_configured", lambda: False)
    monkeypatch.setattr(_run_all, "_llm_configured", lambda: False)
    monkeypatch.setattr(_run_all, "get_data_paths", lambda: _FakePaths(tmp_path))
    monkeypatch.setattr(
        "package.config.load_config",
        lambda *a, **k: {"component_benchmarks": {"datasets": {"grounding": "ds.jsonl"}}},
    )
    called = []
    monkeypatch.setattr(_run_all.subprocess, "run", lambda *a, **k: called.append(a) or None)

    results = _run_all.run_all_benchmarks(output_dir=tmp_path / "out")

    assert results["grounding"]["status"] == "skipped_no_credentials"
    assert called == []  # không chạy subprocess nào cho grounding
    agg = _run_all.aggregate_results(results)
    assert agg["components"]["grounding"]["status"] == "skipped_no_credentials"
    assert agg["summary"]["skipped_components"] == 2  # grounding + multi_turn


def test_backlog_dataset_skipped_by_default(monkeypatch, tmp_path):
    """backlog_datasets + run_backlog=false -> status skipped_backlog, không subprocess."""
    monkeypatch.setattr(_run_all, "_jev_configured", lambda: True)
    monkeypatch.setattr(_run_all, "_llm_configured", lambda: False)
    monkeypatch.setattr(_run_all, "get_data_paths", lambda: _FakePaths(tmp_path))
    monkeypatch.setattr(
        "package.config.load_config",
        lambda *a, **k: {"component_benchmarks": {
            "datasets": {"dummy": "d.jsonl"},
            "run_backlog": False,
            "backlog_datasets": {"planner_backlog": {"component": "planner", "dataset": "bl.jsonl"}},
        }},
    )
    called = []

    def fake_run(cmd, **kwargs):
        called.append(cmd)
        return type("R", (), {"returncode": 0, "stdout": "Results saved to: out/d.json\n", "stderr": ""})()

    monkeypatch.setattr(_run_all.subprocess, "run", fake_run)

    results = _run_all.run_all_benchmarks(output_dir=tmp_path / "out")

    assert results["planner_backlog"]["status"] == "skipped_backlog"
    assert results["planner_backlog"]["backlog"] is True
    assert len(called) == 1 and "d.jsonl" in called[0]  # chỉ dummy chạy, backlog không
    agg = _run_all.aggregate_results(results)
    assert agg["components"]["planner_backlog"]["status"] == "skipped_backlog"
    assert agg["components"]["planner_backlog"]["backlog"] is True
    assert agg["summary"]["skipped_components"] == 2  # planner_backlog + multi_turn


def test_backlog_dataset_runs_when_enabled(monkeypatch, tmp_path):
    """run_backlog=true -> backlog chạy qua component CLI thật."""
    monkeypatch.setattr(_run_all, "_jev_configured", lambda: True)
    monkeypatch.setattr(_run_all, "_llm_configured", lambda: False)
    monkeypatch.setattr(_run_all, "get_data_paths", lambda: _FakePaths(tmp_path))
    monkeypatch.setattr(
        "package.config.load_config",
        lambda *a, **k: {"component_benchmarks": {
            "datasets": {"dummy": "d.jsonl"},
            "run_backlog": True,
            "backlog_datasets": {"planner_backlog": {"component": "planner", "dataset": "bl.jsonl"}},
        }},
    )
    seen = []

    def fake_run(cmd, **kwargs):
        seen.append(cmd)
        return type("R", (), {"returncode": 0, "stdout": "Results saved to: out/bl.json\n", "stderr": ""})()

    monkeypatch.setattr(_run_all.subprocess, "run", fake_run)

    results = _run_all.run_all_benchmarks(output_dir=tmp_path / "out")

    assert results["planner_backlog"]["backlog"] is True
    assert results["planner_backlog"]["result_file"] is not None
    assert any("planner" in c and "bl.jsonl" in c for c in seen)


class _FakePaths:
    def __init__(self, root):
        self._root = root
        self.src_root = root

    def output_dir(self, key):
        d = self._root / key
        d.mkdir(parents=True, exist_ok=True)
        return d
