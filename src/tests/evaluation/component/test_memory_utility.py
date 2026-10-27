"""Tests for the paired multi-run memory utility analysis (synthetic scored data, no LLM)."""

from __future__ import annotations

import json
import random

from package.evaluation.component.benchmarks.memory_utility import analyze_metric, main, scope_of

A, B = "planner", "planner_memory"


def _rows(agent, kind, segment, n, value_fn, run, metric="task_success"):
    return [{"request_id": f"{kind}-{segment}-{i}", "agent": agent, "kind": kind, "segment": segment,
             metric: value_fn(i, run)} for i in range(n)]


def _runs(n_runs, n, kind, base, mem, segment="warm", metric="task_success"):
    ra, rb = [], []
    for run in range(n_runs):
        ra.append(_rows(A, kind, segment, n, lambda i, r: base(i, r), run, metric))
        rb.append(_rows(B, kind, segment, n, lambda i, r: mem(i, r), run, metric))
    return ra, rb


def test_scope_split():
    assert scope_of("constrained") == "oracle" and scope_of("cold_text") == "oracle"
    assert scope_of("similar") == "realistic" and scope_of("personalized") == "realistic"


def test_clear_effect_detected_with_enough_pairs_and_runs():
    ra, rb = _runs(3, 40, "similar", lambda i, r: float(i % 4 == 0), lambda i, r: float(i % 4 in (0, 1)))
    g = analyze_metric(ra, rb, A, B, "task_success")["realistic/similar"]
    assert g["n_paired"] == 40 and g["diff"] == 0.25
    assert g["verdict"] == "memory_better" and g["ci_lower"] > 0


def test_no_effect_is_inconclusive():
    rng = random.Random(0)
    ra, rb = _runs(3, 40, "similar", lambda i, r: float(rng.random() < .5), lambda i, r: float(rng.random() < .5))
    assert analyze_metric(ra, rb, A, B, "task_success")["realistic/similar"]["verdict"] == "inconclusive"


def test_single_run_never_gives_a_verdict_and_warns():
    ra, rb = _runs(1, 40, "similar", lambda i, r: 0.0, lambda i, r: 1.0)
    g = analyze_metric(ra, rb, A, B, "task_success")["realistic/similar"]
    assert g["verdict"] == "inconclusive"
    assert any("single run" in w for w in g["warnings"])
    assert g["run_std_baseline"] is None


def test_small_n_is_inconclusive_and_warns():
    ra, rb = _runs(3, 5, "similar", lambda i, r: 0.0, lambda i, r: 1.0)
    g = analyze_metric(ra, rb, A, B, "task_success")["realistic/similar"]
    assert g["verdict"] == "inconclusive" and any("too few pairs" in w for w in g["warnings"])


def test_oracle_and_realistic_are_separate_groups_and_no_overall_group():
    ra1, rb1 = _runs(2, 25, "similar", lambda i, r: 0.0, lambda i, r: 1.0)
    ra2, rb2 = _runs(2, 25, "constrained", lambda i, r: 1.0, lambda i, r: 0.0)
    ra = [x + y for x, y in zip(ra1, ra2)]
    rb = [x + y for x, y in zip(rb1, rb2)]
    res = analyze_metric(ra, rb, A, B, "task_success")
    assert res["realistic"]["diff"] == 1.0 and res["oracle"]["diff"] == -1.0
    assert not any(k in res for k in ("all", "overall", "total"))
    assert any("ORACLE" in w for w in res["oracle"]["warnings"])


def test_unscored_baseline_is_counted_not_dropped():
    """personalized: planner w/o MemoryTool has task_success=None -> no pairs, reported explicitly."""
    ra, rb = _runs(3, 30, "personalized", lambda i, r: None, lambda i, r: 1.0)
    g = analyze_metric(ra, rb, A, B, "task_success")["realistic/personalized"]
    assert g["verdict"] == "no_pairs" and g["n_unscored_baseline"] == 30 and g["n_paired"] == 0


def test_cost_metric_direction():
    ra, rb = _runs(3, 40, "similar", lambda i, r: 100.0, lambda i, r: 200.0, metric="completion_tokens")
    g = analyze_metric(ra, rb, A, B, "completion_tokens")["realistic/similar"]
    assert g["diff"] == 100.0 and g["verdict"] == "memory_worse"  # more tokens = worse


def test_run_std_reflects_llm_noise():
    ra, rb = _runs(3, 30, "similar", lambda i, r: float(r), lambda i, r: 1.0)
    g = analyze_metric(ra, rb, A, B, "task_success")["realistic/similar"]
    assert g["run_std_baseline"] == 1.0 and g["run_std_memory"] == 0.0


def test_cli_end_to_end(tmp_path, capsys):
    dirs = []
    for run in range(3):
        d = tmp_path / f"exp_{run}"
        d.mkdir()
        rows = (_rows(A, "similar", "warm", 25, lambda i, r: float(i % 2 == 0), run)
                + _rows(B, "similar", "warm", 25, lambda i, r: 1.0, run)
                + _rows(B, "constrained", "warm", 25, lambda i, r: 1.0, run))
        (d / "scored.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        dirs.append(str(d))
    out = tmp_path / "out"
    assert main(["--dirs", *dirs, "--metrics", "task_success", "--out-dir", str(out), "--resamples", "500"]) == 0
    data = json.loads((out / "memory_utility.json").read_text())
    assert data["meta"]["runs_a"] == 3
    assert data["result"]["task_success"]["realistic/similar"]["verdict"] == "memory_better"
    assert data["result"]["task_success"]["oracle/constrained"]["verdict"] == "no_pairs"
    assert (out / "memory_utility.md").exists()
