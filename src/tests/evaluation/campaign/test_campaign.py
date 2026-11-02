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
    """Test CampaignRunner with simulated experiment execution."""
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

    runner = CampaignRunner(campaign, git_sha="test_sha")
    result = runner.run_campaign()

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

    # Override simulation to fail exp_fail
    original_simulate = CampaignRunner._simulate_experiment_run

    def failing_simulate(self, experiment, output_dir):
        if experiment.name == "exp_fail":
            raise ValueError("Simulated failure")
        return original_simulate(self, experiment, output_dir)

    CampaignRunner._simulate_experiment_run = failing_simulate

    try:
        runner = CampaignRunner(campaign)
        result = runner.run_campaign()

        assert result.summary["total_runs"] == 2
        assert result.summary["successful_runs"] == 1
        assert result.summary["failed_runs"] == 1
    finally:
        CampaignRunner._simulate_experiment_run = original_simulate


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
