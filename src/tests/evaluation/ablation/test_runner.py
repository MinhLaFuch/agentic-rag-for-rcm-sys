"""Tests for run_ablation_contrasts — the shared contrast executor."""

import json
from pathlib import Path

import yaml

from package.evaluation.ablation import run_ablation_contrasts
from package.evaluation.ablation._limits import AblationLimits


def _exp_dir(base: Path, name: str, agent_rows: list[dict]) -> Path:
    """Minimal experiment dir: config.yaml + scored.jsonl."""
    d = base / name
    d.mkdir(parents=True)
    config = {
        "config": {
            "seed": 42,
            "per_segment": 20,
            "language": "en",
            "k": 10,
            "eval_schema_version": 2,
        },
        "dataset": {"eval_on": "validation"},
    }
    (d / "config.yaml").write_text(yaml.dump(config), encoding="utf-8")
    (d / "scored.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in agent_rows), encoding="utf-8"
    )
    return d


def _row(request_id: str, agent: str, success: bool) -> dict:
    return {
        "request_id": request_id,
        "agent": agent,
        "kind": "similar",
        "segment": "sparse",
        "task_success": success,
        "recall@10": 0.5 if success else 0.0,
    }


def _limits() -> AblationLimits:
    return AblationLimits(
        bootstrap_resamples=50,
        confidence=0.95,
        min_n_warn=5,
        seed=42,
        metrics=["task_success", "recall@10"],
        groups={},
        contrasts=[],
        output_subdir="test",
    )


def _contrast(name: str = "c1") -> dict:
    return {
        "name": name,
        "a": ["planner", "exp_a"],
        "b": ["planner_memory", "exp_b"],
    }


def test_run_ablation_contrasts_writes_artifacts(tmp_path):
    dir_a = _exp_dir(tmp_path, "exp_a", [_row("r1", "planner", True), _row("r2", "planner", False)])
    dir_b = _exp_dir(tmp_path, "exp_b", [_row("r1", "planner_memory", True), _row("r2", "planner_memory", True)])

    summary = run_ablation_contrasts(
        limits=_limits(),
        groups={"exp_a": [dir_a], "exp_b": [dir_b]},
        contrasts=[_contrast()],
        output_dir=tmp_path / "out",
    )

    assert summary["status"] == "completed"
    assert summary["contrasts"]["c1"]["status"] == "ok"
    cdir = tmp_path / "out" / "c1"
    for f in ("report.md", "comparison.json", "comparison.csv", "disagreements.jsonl"):
        assert (cdir / f).exists(), f"missing {f}"


def test_run_ablation_contrasts_error_does_not_sink_others(tmp_path):
    dir_a = _exp_dir(tmp_path, "exp_a", [_row("r1", "planner", True)])
    dir_b = _exp_dir(tmp_path, "exp_b", [_row("r1", "planner_memory", True)])

    contrasts = [
        {"name": "bad", "a": ["planner", "missing_group"], "b": ["planner_memory", "exp_b"]},
        _contrast("good"),
    ]
    summary = run_ablation_contrasts(
        limits=_limits(),
        groups={"exp_a": [dir_a], "exp_b": [dir_b]},
        contrasts=contrasts,
        output_dir=tmp_path / "out",
    )

    assert summary["contrasts"]["bad"]["status"] == "error"
    assert summary["contrasts"]["good"]["status"] == "ok"
    assert summary["status"] == "partial"


def test_run_ablation_contrasts_missing_scored_is_error_not_crash(tmp_path):
    dir_a = _exp_dir(tmp_path, "exp_a", [_row("r1", "planner", True)])
    dir_b = tmp_path / "exp_b"  # config.yaml present, scored.jsonl missing
    dir_b.mkdir()
    (dir_b / "config.yaml").write_text(yaml.dump({"config": {}, "dataset": {}}), encoding="utf-8")

    summary = run_ablation_contrasts(
        limits=_limits(),
        groups={"exp_a": [dir_a], "exp_b": [dir_b]},
        contrasts=[_contrast()],
        output_dir=tmp_path / "out",
    )
    assert summary["contrasts"]["c1"]["status"] == "error"
    assert "scored.jsonl" in summary["contrasts"]["c1"]["error"]
