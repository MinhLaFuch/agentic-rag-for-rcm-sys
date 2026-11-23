"""Tests for campaign-integrated ablation contrasts."""

import json
from pathlib import Path

import yaml

from package.evaluation.campaign._schema import CampaignConfig, CampaignResult, ExperimentRun
from package.evaluation.campaign.campaign_runner import CampaignRunner


def _exp_dir(base: Path, name: str, agent: str, successes: list[bool]) -> Path:
    d = base / name / "run_1"
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
    rows = [
        {
            "request_id": f"r{i}",
            "agent": agent,
            "kind": "similar",
            "segment": "sparse",
            "task_success": s,
            "recall@10": 0.5 if s else 0.0,
        }
        for i, s in enumerate(successes)
    ]
    (d / "scored.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )
    return d


def _runner(tmp_path: Path, contrasts: list[dict]) -> CampaignRunner:
    cfg = CampaignConfig(
        campaign_id="camp_t",
        ablation={"contrasts": contrasts},
    )
    return CampaignRunner(cfg)


def _runs(*specs) -> list[ExperimentRun]:
    return [
        ExperimentRun(
            experiment_name=name,
            run_number=1,
            output_dir="x",
            experiment_dir=str(d),
            success=success,
        )
        for name, d, success in specs
    ]


def test_run_ablation_disabled_without_contrasts(tmp_path):
    runner = CampaignRunner(CampaignConfig(campaign_id="camp_t"))
    assert runner._run_ablation([], tmp_path) == {"status": "disabled"}


def test_run_ablation_resolves_experiment_names_to_run_dirs(tmp_path):
    dir_a = _exp_dir(tmp_path, "exp_a", "planner", [True, False])
    dir_b = _exp_dir(tmp_path, "exp_b", "planner_memory", [True, True])
    runner = _runner(tmp_path, [{
        "name": "mem_effect",
        "a": ["planner", "exp_a"],
        "b": ["planner_memory", "exp_b"],
    }])
    out = tmp_path / "campaign_out"
    summary = runner._run_ablation(
        _runs(("exp_a", dir_a, True), ("exp_b", dir_b, True)), out
    )
    assert summary["status"] == "completed"
    assert summary["contrasts"]["mem_effect"]["status"] == "ok"
    assert (out / "ablation" / "mem_effect" / "report.md").exists()
    assert (out / "ablation" / "mem_effect" / "comparison.json").exists()


def test_run_ablation_unknown_experiment_is_error_not_crash(tmp_path):
    dir_b = _exp_dir(tmp_path, "exp_b", "planner_memory", [True])
    runner = _runner(tmp_path, [{
        "name": "c1",
        "a": ["planner", "exp_missing"],
        "b": ["planner_memory", "exp_b"],
    }])
    summary = runner._run_ablation(
        _runs(("exp_b", dir_b, True)), tmp_path / "out"
    )
    assert summary["contrasts"]["c1"]["status"] == "error"


def test_run_ablation_skips_failed_runs(tmp_path):
    dir_ok = _exp_dir(tmp_path, "exp_b", "planner_memory", [True])
    runner = _runner(tmp_path, [{
        "name": "c1",
        "a": ["planner", "exp_a"],
        "b": ["planner_memory", "exp_b"],
    }])
    # exp_a failed -> not in groups -> contrast errors, doesn't crash
    summary = runner._run_ablation(
        _runs(("exp_a", tmp_path / "nonexistent", False), ("exp_b", dir_ok, True)),
        tmp_path / "out",
    )
    assert summary["contrasts"]["c1"]["status"] == "error"


def test_campaign_result_ablation_roundtrip(tmp_path):
    result = CampaignResult(
        campaign_id="c",
        campaign_hash="h",
        ablation={"status": "completed", "contrasts": {"c1": {"status": "ok"}}},
    )
    path = tmp_path / "campaign_result.json"
    path.write_text(json.dumps(result.to_dict()), encoding="utf-8")
    loaded = CampaignResult.from_dict(json.loads(path.read_text(encoding="utf-8")))
    assert loaded.ablation["contrasts"]["c1"]["status"] == "ok"


def test_campaign_config_ablation_roundtrip(tmp_path):
    cfg = CampaignConfig(
        campaign_id="c",
        ablation={"contrasts": [{"name": "x", "a": ["p", "e1"], "b": ["p", "e2"]}]},
    )
    path = tmp_path / "campaign.yaml"
    cfg.to_yaml(path)
    loaded = CampaignConfig.from_yaml(path)
    assert loaded.ablation["contrasts"][0]["name"] == "x"
