"""Tests for --only subset runs of a campaign."""

import json
from pathlib import Path

import pytest

from package.evaluation.campaign import (
    CampaignConfig,
    ExperimentConfig,
    CampaignResult,
    ExperimentRun,
    CampaignRunner,
)


def _grid_campaign(tmp_path: Path) -> CampaignConfig:
    """3 experiments named exp_1..exp_3 via parameter grid (positional IDs)."""
    return CampaignConfig(
        campaign_id="subset_test",
        dataset={"path": "data/test.jsonl"},
        parameter_grid={
            "agents": [["baseline"], ["planner"], ["planner_memory"]],
            "reflect_rounds": [0],
        },
        output_dir=str(tmp_path / "campaign_output"),
    )


def _fake_run_factory(calls: list[str]):
    def fake_run(self, experiment, run_number, output_dir, multi_turn=None):
        calls.append(experiment.name)
        return ExperimentRun(
            experiment_name=experiment.name,
            run_number=run_number,
            output_dir=str(output_dir / experiment.name / f"run_{run_number}"),
            success=True,
            metrics={"task_success_rate": 0.8},
            git_sha=self.git_sha,
        )
    return fake_run


def test_only_selects_by_grid_position_ids(tmp_path):
    """--only 1,3 runs exactly exp_1_* and exp_3_*; names are NOT renumbered."""
    campaign = _grid_campaign(tmp_path)
    experiments = campaign.expand_parameter_grid()
    names = [e.name for e in experiments]
    assert names[0].startswith("exp_1_") and names[-1].startswith("exp_3_")

    selected, skipped = CampaignRunner._select_experiments(experiments, ["1", "exp_3"])
    assert [e.name for e in selected] == [names[0], names[2]]
    assert skipped == [names[1]]


def test_only_unknown_id_raises(tmp_path):
    """An unmatched --only token is an error, never a silent skip."""
    campaign = _grid_campaign(tmp_path)
    experiments = campaign.expand_parameter_grid()
    with pytest.raises(ValueError, match="no experiment matches"):
        CampaignRunner._select_experiments(experiments, ["99"])
    with pytest.raises(ValueError, match="no experiment matches"):
        CampaignRunner._select_experiments(experiments, ["bogus_name"])


def test_subset_run_only_touches_selected(tmp_path):
    """Skipped experiments get no _run_experiment call and no output dir."""
    campaign = _grid_campaign(tmp_path)
    calls: list[str] = []
    original = CampaignRunner._run_experiment
    CampaignRunner._run_experiment = _fake_run_factory(calls)
    try:
        result = CampaignRunner(campaign, git_sha="sha_subset").run_campaign(only=["2"])
    finally:
        CampaignRunner._run_experiment = original

    assert calls == [e.name for e in campaign.expand_parameter_grid() if e.name.startswith("exp_2_")]
    out = Path(campaign.output_dir)
    for d in out.iterdir():
        if d.is_dir():
            assert d.name.startswith("exp_2_")
    assert result.subset["comparisons"] == "skipped_subset_run"
    assert len(result.subset["skipped"]) == 2
    assert result.comparisons == {}
    # new runs carry the git_sha of this run
    assert all(r.git_sha == "sha_subset" for r in result.runs)


def test_subset_run_merges_previous_result(tmp_path):
    """campaign_result.json keeps skipped entries, preserves comparisons, backs up."""
    campaign = _grid_campaign(tmp_path)
    out = Path(campaign.output_dir)
    out.mkdir(parents=True)
    # Previous full-run result uses the REAL positional names: exp_1/exp_3 done,
    # exp_2 failed (the campaign_001 rerun scenario).
    real_names = [e.name for e in campaign.expand_parameter_grid()]
    n1 = [n for n in real_names if n.startswith("exp_1_")][0]
    n2 = [n for n in real_names if n.startswith("exp_2_")][0]
    n3 = [n for n in real_names if n.startswith("exp_3_")][0]
    prev = CampaignResult(
        campaign_id=campaign.campaign_id,
        campaign_hash="oldhash",
        runs=[
            ExperimentRun(experiment_name=n1, run_number=1, output_dir="o1", success=True,
                          metrics={"task_success_rate": 0.5}),
            ExperimentRun(experiment_name=n2, run_number=1, output_dir="o2", success=False,
                          error="timed out"),
            ExperimentRun(experiment_name=n3, run_number=1, output_dir="o3", success=True,
                          metrics={"task_success_rate": 0.7}),
        ],
        comparisons={f"{n1}_vs_{n3}": {"status": "success"}},
        summary={"total_runs": 3},
    )
    (out / "campaign_result.json").write_text(json.dumps(prev.to_dict()), encoding="utf-8")

    calls: list[str] = []

    def fake_run(self, experiment, run_number, output_dir, multi_turn=None):
        calls.append(experiment.name)
        return ExperimentRun(
            experiment_name=experiment.name,
            run_number=run_number,
            output_dir=str(output_dir / experiment.name / f"run_{run_number}"),
            success=True,
            metrics={"task_success_rate": 0.9},
            git_sha=self.git_sha,
        )

    original = CampaignRunner._run_experiment
    CampaignRunner._run_experiment = fake_run
    try:
        result = CampaignRunner(campaign, git_sha="sha2").run_campaign(only=["2"])
    finally:
        CampaignRunner._run_experiment = original

    on_disk = json.loads((out / "campaign_result.json").read_text(encoding="utf-8"))
    by_name = {r["experiment_name"]: r for r in on_disk["runs"]}
    assert len(on_disk["runs"]) == 3
    # skipped exp_1/exp_3 keep OLD entries verbatim (old metrics, no git_sha)
    assert by_name[n1]["metrics"]["task_success_rate"] == 0.5 and by_name[n1]["git_sha"] == ""
    assert by_name[n3]["metrics"]["task_success_rate"] == 0.7
    # re-run exp_2 entry REPLACED by the new successful run
    assert by_name[n2]["success"] is True
    assert by_name[n2]["metrics"]["task_success_rate"] == 0.9
    assert by_name[n2]["git_sha"] == "sha2"
    # comparisons preserved from previous full run
    assert on_disk["comparisons"] == {f"{n1}_vs_{n3}": {"status": "success"}}
    # summary recomputed over merged runs (3 entries, 3 successful now)
    assert on_disk["summary"]["total_runs"] == 3
    assert on_disk["summary"]["successful_runs"] == 3
    # subset metadata + backup file
    assert on_disk["subset"]["only"] == ["2"]
    assert on_disk["subset"]["skipped"] == [n1, n3]
    assert list(out.glob("campaign_result_backup_*.json"))


def test_full_run_without_only_unchanged(tmp_path):
    """Regression: no --only -> all experiments run, auto comparisons, no subset field."""
    campaign = _grid_campaign(tmp_path)
    calls: list[str] = []
    original = CampaignRunner._run_experiment
    CampaignRunner._run_experiment = _fake_run_factory(calls)
    try:
        result = CampaignRunner(campaign).run_campaign()
    finally:
        CampaignRunner._run_experiment = original

    assert len(calls) == 3
    assert len(result.runs) == 3
    assert result.subset == {}
    assert result.comparisons  # auto-generated pairs vs first experiment still work
