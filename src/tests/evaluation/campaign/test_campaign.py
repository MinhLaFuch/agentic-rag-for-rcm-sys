"""Tests for campaign orchestration."""

import pytest
from pathlib import Path
import json

from package.evaluation.campaign import (
    CampaignConfig,
    ExperimentConfig,
    CampaignResult,
    ExperimentRun,
    CampaignRunner,
    CheckpointManager,
    CAMPAIGN_VERSION,
)


def test_experiment_config_serialization():
    """Test ExperimentConfig serialization round-trip."""
    config = ExperimentConfig(
        name="test_exp",
        description="Test experiment",
        agent_config={"model": "gpt-4"},
        evaluation_config={"layers": [1, 2, 3]},
        dataset={"path": "data/test.jsonl"},
        repetition_count=3,
        random_seed=42,
        tags=["test"],
    )

    data = config.to_dict()
    restored = ExperimentConfig.from_dict(data)

    assert restored.name == config.name
    assert restored.description == config.description
    assert restored.agent_config == config.agent_config
    assert restored.repetition_count == config.repetition_count


def test_campaign_config_serialization():
    """Test CampaignConfig serialization round-trip."""
    campaign = CampaignConfig(
        campaign_id="test_campaign",
        description="Test campaign",
        dataset={"path": "data/test.jsonl"},
        experiments=[
            ExperimentConfig(name="exp1", description="Experiment 1"),
            ExperimentConfig(name="exp2", description="Experiment 2"),
        ],
        output_dir="experiments/test",
        comparison_pairs=[("exp1", "exp2")],
        statistical_settings={"confidence_level": 0.95},
    )

    data = campaign.to_dict()
    restored = CampaignConfig.from_dict(data)

    assert restored.campaign_id == campaign.campaign_id
    assert len(restored.experiments) == 2
    assert restored.comparison_pairs == campaign.comparison_pairs


def test_campaign_config_yaml_io(tmp_path: Path):
    """Test CampaignConfig YAML I/O."""
    campaign = CampaignConfig(
        campaign_id="test_campaign",
        description="Test campaign",
        dataset={"path": "data/test.jsonl"},
        experiments=[
            ExperimentConfig(name="exp1", description="Experiment 1"),
        ],
        output_dir="experiments/test",
    )

    yaml_path = tmp_path / "campaign.yaml"
    campaign.to_yaml(yaml_path)

    restored = CampaignConfig.from_yaml(yaml_path)

    assert restored.campaign_id == campaign.campaign_id
    assert len(restored.experiments) == 1


def test_campaign_config_hash():
    """Test campaign hash computation."""
    campaign1 = CampaignConfig(
        campaign_id="test_campaign",
        dataset={"path": "data/test.jsonl"},
        experiments=[
            ExperimentConfig(name="exp1", agent_config={"model": "gpt-4"}),
        ],
    )

    campaign2 = CampaignConfig(
        campaign_id="test_campaign",
        dataset={"path": "data/test.jsonl"},
        experiments=[
            ExperimentConfig(name="exp1", agent_config={"model": "gpt-4"}),
        ],
    )

    # Same config should produce same hash
    assert campaign1.compute_hash() == campaign2.compute_hash()

    # Different config should produce different hash
    campaign3 = CampaignConfig(
        campaign_id="test_campaign",
        dataset={"path": "data/test.jsonl"},
        experiments=[
            ExperimentConfig(name="exp1", agent_config={"model": "gpt-3.5"}),
        ],
    )

    assert campaign1.compute_hash() != campaign3.compute_hash()


def test_experiment_run_serialization():
    """Test ExperimentRun serialization round-trip."""
    run = ExperimentRun(
        experiment_name="test_exp",
        run_number=1,
        output_dir="experiments/test/run_1",
        success=True,
        metrics={"task_success_rate": 0.85},
    )

    data = run.to_dict()
    restored = ExperimentRun.from_dict(data)

    assert restored.experiment_name == run.experiment_name
    assert restored.run_number == run.run_number
    assert restored.success == run.success


def test_campaign_result_serialization():
    """Test CampaignResult serialization round-trip."""
    result = CampaignResult(
        campaign_id="test_campaign",
        campaign_hash="abc123",
        runs=[
            ExperimentRun(
                experiment_name="exp1",
                run_number=1,
                output_dir="experiments/exp1/run_1",
                success=True,
            ),
        ],
        summary={"total_runs": 1, "successful_runs": 1},
    )

    data = result.to_dict()
    restored = CampaignResult.from_dict(data)

    assert restored.campaign_id == result.campaign_id
    assert len(restored.runs) == 1


def test_campaign_runner_simulation(tmp_path: Path):
    """Test CampaignRunner orchestration with a stubbed _run_experiment (no subprocess)."""
    campaign = CampaignConfig(
        campaign_id="test_campaign",
        dataset={"path": "data/test.jsonl"},
        experiments=[
            ExperimentConfig(
                name="exp1",
                description="Experiment 1",
                repetition_count=2,
            ),
            ExperimentConfig(
                name="exp2",
                description="Experiment 2",
                repetition_count=1,
            ),
        ],
        output_dir=str(tmp_path / "campaign_output"),
        comparison_pairs=[("exp1", "exp2")],
    )

    original_run = CampaignRunner._run_experiment

    def fake_run(self, experiment, run_number, output_dir, multi_turn_output_dir=None):
        return ExperimentRun(
            experiment_name=experiment.name,
            run_number=run_number,
            output_dir=str(output_dir / experiment.name / f"run_{run_number}"),
            success=True,
            metrics={"task_success_rate": 0.8},
        )

    CampaignRunner._run_experiment = fake_run

    try:
        runner = CampaignRunner(campaign, git_sha="test_sha")
        result = runner.run_campaign()
    finally:
        CampaignRunner._run_experiment = original_run

    assert result.campaign_id == campaign.campaign_id
    assert len(result.runs) == 3  # 2 runs for exp1 + 1 run for exp2
    assert result.summary["total_runs"] == 3
    assert result.summary["successful_runs"] == 3
    assert "exp1_vs_exp2" in result.comparisons


def test_campaign_runner_with_failed_experiment(tmp_path: Path):
    """Test CampaignRunner handles failed experiments."""
    campaign = CampaignConfig(
        campaign_id="test_campaign",
        dataset={"path": "data/test.jsonl"},
        experiments=[
            ExperimentConfig(
                name="exp_success",
                description="Successful experiment",
                repetition_count=1,
            ),
            ExperimentConfig(
                name="exp_fail",
                description="Failing experiment",
                repetition_count=1,
            ),
        ],
        output_dir=str(tmp_path / "campaign_output"),
    )

    # Override _run_experiment (the per-experiment unit) so no subprocess runs
    original_run = CampaignRunner._run_experiment

    def fake_run(self, experiment, run_number, output_dir, multi_turn_output_dir=None):
        success = experiment.name != "exp_fail"
        return ExperimentRun(
            experiment_name=experiment.name,
            run_number=run_number,
            output_dir=str(output_dir / experiment.name / f"run_{run_number}"),
            success=success,
            error=None if success else "Simulated failure",
            metrics={"task_success_rate": 0.9} if success else {},
        )

    CampaignRunner._run_experiment = fake_run

    try:
        runner = CampaignRunner(campaign)
        result = runner.run_campaign()

        assert result.summary["total_runs"] == 2
        assert result.summary["successful_runs"] == 1
        assert result.summary["failed_runs"] == 1
    finally:
        CampaignRunner._run_experiment = original_run


def test_checkpoint_manager(tmp_path: Path):
    """Test CheckpointManager save and load."""
    result = CampaignResult(
        campaign_id="test_campaign",
        campaign_hash="abc123",
        runs=[
            ExperimentRun(
                experiment_name="exp1",
                run_number=1,
                output_dir="experiments/exp1/run_1",
                success=True,
            ),
        ],
    )

    manager = CheckpointManager(tmp_path)
    manager.save_checkpoint(result)

    loaded = manager.load_checkpoint()

    assert loaded is not None
    assert loaded.campaign_id == result.campaign_id
    assert len(loaded.runs) == 1


def test_checkpoint_manager_clear(tmp_path: Path):
    """Test CheckpointManager clear."""
    result = CampaignResult(
        campaign_id="test_campaign",
        campaign_hash="abc123",
        runs=[],
    )

    manager = CheckpointManager(tmp_path)
    manager.save_checkpoint(result)

    assert manager.checkpoint_file.exists()

    manager.clear_checkpoint()

    assert not manager.checkpoint_file.exists()


def test_checkpoint_manager_no_checkpoint(tmp_path: Path):
    """Test CheckpointManager load when no checkpoint exists."""
    manager = CheckpointManager(tmp_path)
    loaded = manager.load_checkpoint()

    assert loaded is None


def test_experiment_comparison():
    """Test experiment comparison logic."""
    runs_a = [
        ExperimentRun(
            experiment_name="exp_a",
            run_number=1,
            output_dir="exp_a/run_1",
            success=True,
            metrics={"task_success_rate": 0.80, "latency": 1.0},
        ),
        ExperimentRun(
            experiment_name="exp_a",
            run_number=2,
            output_dir="exp_a/run_2",
            success=True,
            metrics={"task_success_rate": 0.85, "latency": 1.1},
        ),
    ]

    runs_b = [
        ExperimentRun(
            experiment_name="exp_b",
            run_number=1,
            output_dir="exp_b/run_1",
            success=True,
            metrics={"task_success_rate": 0.90, "latency": 0.9},
        ),
    ]

    runner = CampaignRunner(CampaignConfig(campaign_id="test"))
    comparison = runner._compare_experiments(runs_a, runs_b)

    assert comparison["status"] == "success"
    assert comparison["experiment_a"] == "exp_a"
    assert comparison["experiment_b"] == "exp_b"
    assert comparison["runs_a"] == 2
    assert comparison["runs_b"] == 1

    # Check task_success_rate delta
    tsr_delta = comparison["deltas"]["task_success_rate"]
    assert tsr_delta["a"] == pytest.approx(0.825)  # Average of 0.80 and 0.85
    assert tsr_delta["b"] == 0.90
    assert tsr_delta["delta"] == pytest.approx(0.075)


def test_campaign_example_yaml_loads():
    """Test that the example campaign YAML can be loaded."""
    example_path = Path(__file__).parent.parent / "campaign" / "example_campaign.yaml"

    if example_path.exists():
        campaign = CampaignConfig.from_yaml(example_path)

        assert campaign.campaign_id == "campaign_001_baseline_vs_improved"
        assert len(campaign.experiments) == 4
        assert len(campaign.comparison_pairs) == 5
        assert campaign.statistical_settings["confidence_level"] == 0.95


def test_build_config_overlay_maps_known_keys():
    """_build_config_overlay maps agent_config/evaluation_config/random_seed into overlay shape."""
    runner = CampaignRunner(CampaignConfig(campaign_id="camp_x"))
    exp = ExperimentConfig(
        name="exp_a",
        agent_config={"agents": ["baseline"], "inference_mode": "template", "reflect_rounds": 2},
        evaluation_config={"per_segment": 5},
        random_seed=7,
    )
    ov = runner._build_config_overlay(exp, 3)

    ae = ov["agent/agent_eval"]["agent_eval"]
    assert ae["agents"] == ["baseline"]
    assert ae["per_segment"] == 5
    assert ae["trajectory_file"] == "camp_x_exp_a_run3_trajectories.jsonl"
    assert ov["agent/inference"]["inference"]["mode"] == "template"
    assert ov["agent/agent"]["agent"]["reflect_rounds"] == 2
    assert ov["eval/baselines"]["baselines"]["seed"] == 7


def test_build_config_overlay_uses_campaign_defaults():
    """Defaults (agents, allow_missing_corpus_sources) come from CampaignConfig, not literals."""
    runner = CampaignRunner(CampaignConfig(
        campaign_id="c",
        default_agents=["planner"],
        allow_missing_corpus_sources=False,
    ))
    ov = runner._build_config_overlay(ExperimentConfig(name="e"), 1)
    ae = ov["agent/agent_eval"]["agent_eval"]
    assert ae["agents"] == ["planner"]
    assert ae["allow_missing_corpus_sources"] is False


def test_build_config_overlay_rejects_unmapped_keys():
    """Unknown agent_config/evaluation_config keys raise instead of being dropped."""
    runner = CampaignRunner(CampaignConfig(campaign_id="c"))
    with pytest.raises(ValueError, match="unmapped config keys"):
        runner._build_config_overlay(ExperimentConfig(name="e", agent_config={"bogus": 1}), 1)
    with pytest.raises(ValueError, match="unmapped config keys"):
        runner._build_config_overlay(ExperimentConfig(name="e", evaluation_config={"bogus": 1}), 1)


def test_load_experiment_metrics_from_stdout(tmp_path: Path):
    """_load_experiment_metrics parses 'saved -> <dir>' and flattens metrics.json."""
    exp_dir = tmp_path / "exp_042"
    exp_dir.mkdir()
    (exp_dir / "metrics.json").write_text(json.dumps({
        "k": 10,
        "summary": {"planner": {"similar": {"all": {"task_success": 0.9, "n": 20}}}},
    }), encoding="utf-8")

    runner = CampaignRunner(CampaignConfig(campaign_id="c"))
    metrics = runner._load_experiment_metrics(f"some output\nsaved -> {exp_dir}\n")
    assert metrics["planner_similar_task_success"] == 0.9

    # No 'saved ->' line or missing file -> empty dict, not an exception
    assert runner._load_experiment_metrics("no save line") == {}
    assert runner._load_experiment_metrics(f"saved -> {tmp_path / 'nope'}") == {}


def test_auto_comparison_pairs_are_actually_used(tmp_path: Path):
    """parameter_grid + empty comparison_pairs -> auto-generated pairs must reach _run_comparisons."""
    campaign = CampaignConfig(
        campaign_id="grid_campaign",
        dataset={"path": "data/test.jsonl"},
        parameter_grid={"inference_mode": ["template", "llm"]},
        comparison_pairs=[],
        output_dir=str(tmp_path / "out"),
    )

    original_run = CampaignRunner._run_experiment

    def fake_run(self, experiment, run_number, output_dir, multi_turn_output_dir=None):
        return ExperimentRun(
            experiment_name=experiment.name,
            run_number=run_number,
            output_dir=str(output_dir / experiment.name / f"run_{run_number}"),
            success=True,
            metrics={"task_success_rate": 0.8},
        )

    CampaignRunner._run_experiment = fake_run
    try:
        result = CampaignRunner(campaign).run_campaign()
    finally:
        CampaignRunner._run_experiment = original_run

    assert result.comparisons, "auto-generated comparison pairs were dropped"
    (pair_key,) = result.comparisons.keys()
    assert pair_key.endswith("_vs_" + pair_key.split("_vs_")[-1])
    assert result.comparisons[pair_key]["status"] == "success"


def test_build_config_overlay_includes_campaign_id():
    """campaign_id must reach the per-experiment config overlay for traceability."""
    runner = CampaignRunner(CampaignConfig(campaign_id="camp_trace"))
    ov = runner._build_config_overlay(ExperimentConfig(name="e"), 1)
    assert ov["agent/agent_eval"]["agent_eval"]["campaign_id"] == "camp_trace"


def test_load_experiment_metrics_excludes_sample_count(tmp_path: Path):
    """'n' (sample count) must not leak into comparison metrics."""
    exp_dir = tmp_path / "exp_n"
    exp_dir.mkdir()
    (exp_dir / "metrics.json").write_text(json.dumps({
        "k": 10,
        "summary": {"planner": {"similar": {"all": {"task_success": 0.9, "n": 20}}}},
    }), encoding="utf-8")

    runner = CampaignRunner(CampaignConfig(campaign_id="c"))
    metrics = runner._load_experiment_metrics(f"saved -> {exp_dir}")
    assert metrics["planner_similar_task_success"] == 0.9
    assert "planner_similar_n" not in metrics


def _stat_runs(name_a="exp_a", name_b="exp_b", n=3):
    runs_a = [
        ExperimentRun(
            experiment_name=name_a, run_number=i + 1, output_dir=f"{name_a}/r{i}",
            success=True, metrics={"task_success_rate": 0.80 + 0.01 * i},
        )
        for i in range(n)
    ]
    runs_b = [
        ExperimentRun(
            experiment_name=name_b, run_number=i + 1, output_dir=f"{name_b}/r{i}",
            success=True, metrics={"task_success_rate": 0.90 + 0.01 * i},
        )
        for i in range(n)
    ]
    return runs_a, runs_b


def test_statistical_settings_produce_ci_and_paired_delta():
    """statistical_settings from campaign.yaml drives bootstrap CIs (Phase 4.1)."""
    cfg = CampaignConfig(
        campaign_id="stat_test",
        statistical_settings={
            "confidence_level": 0.95,
            "bootstrap_samples": 200,
            "paired_comparison": True,
            "random_seed": 7,
        },
    )
    runner = CampaignRunner(cfg)
    runs_a, runs_b = _stat_runs()
    comparison = runner._compare_experiments(runs_a, runs_b)

    assert comparison["statistics"]["confidence_level"] == 0.95
    assert comparison["statistics"]["bootstrap_samples"] == 200

    tsr = comparison["deltas"]["task_success_rate"]
    # Paired equal-length runs → delta CI + p_value present
    assert "delta_ci" in tsr and "p_value" in tsr and "significant" in tsr
    # B is consistently ~0.10 above A → CI excludes 0 → significant
    assert tsr["significant"] is True
    assert tsr["delta_ci"][0] > 0

    # Per-experiment mean/std/CI across runs
    stats = comparison["metric_stats"]["task_success_rate"]
    assert stats["a"]["n"] == 3 and stats["b"]["n"] == 3
    assert stats["a"]["ci"][0] <= stats["a"]["mean"] <= stats["a"]["ci"][1]


def test_unpaired_or_disabled_statistics_skip_delta_ci():
    """paired_comparison=false or unequal run counts → no delta_ci."""
    cfg = CampaignConfig(
        campaign_id="stat_test2",
        statistical_settings={"paired_comparison": False, "bootstrap_samples": 100},
    )
    runner = CampaignRunner(cfg)
    runs_a, runs_b = _stat_runs()
    comparison = runner._compare_experiments(runs_a, runs_b)
    assert "delta_ci" not in comparison["deltas"]["task_success_rate"]

    # Unequal lengths with paired enabled → also no delta_ci
    cfg2 = CampaignConfig(
        campaign_id="stat_test3",
        statistical_settings={"paired_comparison": True, "bootstrap_samples": 100},
    )
    runner2 = CampaignRunner(cfg2)
    comparison2 = runner2._compare_experiments(runs_a, runs_b[:2])
    assert "delta_ci" not in comparison2["deltas"]["task_success_rate"]


def test_repo_campaign_yaml_still_loads_via_config_system():
    """Regression: configs/evaluation/campaign.yaml parses identically through load_config."""
    from package.config import CONFIG_DIR

    campaign = CampaignConfig.from_yaml(CONFIG_DIR / "evaluation" / "campaign.yaml")

    assert campaign.campaign_id == "campaign_001_parameter_grid"
    assert campaign.statistical_settings["confidence_level"] == 0.95
    assert len(campaign.expand_parameter_grid()) == 12  # 3 agents x 2 modes x 2 reflect_rounds


def test_campaign_config_rejects_unknown_keys(tmp_path):
    """configs/-style campaign files are schema-validated with extra=forbid."""
    from package.config.load_config import ConfigError, load_config

    cfg_dir = tmp_path / "evaluation"
    cfg_dir.mkdir()
    (cfg_dir / "campaign.yaml").write_text('campaign_id: "x"\nbogus_key: 1\n', encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config("evaluation/campaign", config_dir=tmp_path)


def test_campaign_config_overlay_is_honored(tmp_path, monkeypatch):
    """CampaignConfig.from_yaml routes configs/ paths through load_config (CONFIG_OVERLAY_PATH applies)."""
    from package.config import CONFIG_DIR

    overlay = tmp_path / "overlay.yaml"
    overlay.write_text(
        'evaluation/campaign:\n  output_dir: "agent_eval/campaigns/overlaid_test"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("CONFIG_OVERLAY_PATH", str(overlay))

    campaign = CampaignConfig.from_yaml(CONFIG_DIR / "evaluation" / "campaign.yaml")

    assert campaign.output_dir == "agent_eval/campaigns/overlaid_test"


def test_run_experiment_builds_domain_cmd_and_runs_subprocess(tmp_path, monkeypatch):
    """_run_experiment (non-dry-run) must reach subprocess.run: cmd carries --domain
    (no --tag) and traj-path resolution works — regression for the UnboundLocalError
    caused by a stray function-local 'from package.config import get_data_paths'."""
    import subprocess as sp

    exp_dir = tmp_path / "exp_out"
    exp_dir.mkdir()
    (exp_dir / "metrics.json").write_text(json.dumps({"summary": {}}), encoding="utf-8")

    campaign = CampaignConfig(
        campaign_id="c",
        dataset={"split": "validation", "filters": {"domains": ["Video_Games", "Electronics", "Toys_and_Games"]}},
        experiments=[ExperimentConfig(name="exp1")],
        output_dir=str(tmp_path / "campaign_output"),
    )
    runner = CampaignRunner(campaign, git_sha="test_sha")

    captured = {}

    class _Result:
        returncode = 0
        stdout = f"noise\nsaved -> {exp_dir}\n"
        stderr = ""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _Result()

    monkeypatch.setattr(sp, "run", fake_run)

    run = runner._run_experiment(campaign.experiments[0], 1, tmp_path / "out")

    assert run.success is True
    assert run.error is None
    cmd = captured["cmd"]
    assert "--tag" not in cmd
    assert cmd.count("--domain") == 3
    assert "scripts/evaluation/run_agent_eval.py" in " ".join(cmd)


def test_real_campaign_overlay_loads_via_config_system(tmp_path, monkeypatch):
    """Regression: a real CampaignRunner overlay must pass _check_overlay_keys.

    campaign_id was set by the overlay but absent from agent_eval.yaml, so every
    campaign experiment died at startup (ConfigError: unknown key). This drives
    the actual overlay through CONFIG_OVERLAY_PATH + load_config.
    """
    import yaml
    from package.config.load_config import load_config

    runner = CampaignRunner(CampaignConfig(campaign_id="mt_campaign"))
    exp = ExperimentConfig(
        name="exp_a",
        agent_config={"agents": ["baseline"], "inference_mode": "template"},
        evaluation_config={"per_segment": 5},
        random_seed=7,
    )

    for run_number in (1, 2):
        overlay = runner._build_config_overlay(exp, run_number)
        overlay_path = tmp_path / f"overlay_{run_number}.yaml"
        overlay_path.write_text(
            yaml.safe_dump(overlay, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        monkeypatch.setenv("CONFIG_OVERLAY_PATH", str(overlay_path))

        cfg = load_config("agent/agent_eval")["agent_eval"]
        assert cfg["campaign_id"] == "mt_campaign"
        assert cfg["agents"] == ["baseline"]
        assert cfg["per_segment"] == 5
        assert cfg["trajectory_file"] == f"mt_campaign_exp_a_run{run_number}_trajectories.jsonl"

        inference = load_config("agent/inference")["inference"]
        assert inference["mode"] == "template"
        baselines = load_config("eval/baselines")["baselines"]
        assert baselines["seed"] == 7
