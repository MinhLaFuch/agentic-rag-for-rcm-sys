"""Tests for campaign-level multi-turn wiring (Phase B).

Covers: once-per-campaign scheduling, overlay output_dir redirect (artifact
in campaigns/<id>/multi_turn/, never in exp_dir), campaign_result.json
summary, not_run/disabled statuses, and exclusion from paired comparisons.
No subprocesses or LLM calls — _run_experiment is stubbed.
"""

import json
from pathlib import Path

import pytest
import yaml

from package.config.load_config import load_config

from package.evaluation.campaign import (
    CampaignConfig,
    CampaignResult,
    ExperimentConfig,
    ExperimentRun,
    CampaignRunner,
)


def _campaign(tmp_path: Path, *, multi_turn: str = "once", repetitions: int = 1) -> CampaignConfig:
    return CampaignConfig(
        campaign_id="mt_campaign",
        dataset={"path": "data/test.jsonl"},
        experiments=[
            ExperimentConfig(name="exp_first", repetition_count=repetitions),
            ExperimentConfig(name="exp_second", repetition_count=1),
        ],
        output_dir=str(tmp_path / "campaign_output"),
        comparison_pairs=[("exp_first", "exp_second")],
        multi_turn=multi_turn,
    )


def _stub_runs(monkeypatch, fail_first: bool = False):
    def fake_run(self, experiment, run_number, output_dir, multi_turn_output_dir=None):
        success = not (fail_first and experiment.name == "exp_first" and run_number == 1)
        return ExperimentRun(
            experiment_name=experiment.name,
            run_number=run_number,
            output_dir=str(output_dir / experiment.name / f"run_{run_number}"),
            success=success,
            error=None if success else "simulated early failure",
            metrics={"task_success_rate": 0.8},
        )

    monkeypatch.setattr(CampaignRunner, "_run_experiment", fake_run)


def _write_mt_file(output_dir: Path, status: str = "success") -> Path:
    mt_dir = output_dir / "multi_turn"
    mt_dir.mkdir(parents=True, exist_ok=True)
    payload = {"status": status}
    if status == "success":
        payload.update({
            "turn_success_rate": 0.9,
            "conversation_success_rate": 0.8,
            "turn_completion_ratio": 0.95,
            "total_turns_scheduled": 20,
            "total_turns_executed": 19,
            "failed_conversations": 2,
        })
    path = mt_dir / "multi_turn.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class TestMultiTurnScheduling:
    def test_once_only_first_experiment_first_repetition(self, tmp_path):
        runner = CampaignRunner(_campaign(tmp_path))
        out = tmp_path / "campaign_output"
        assert runner._multi_turn_dir_for(0, 1, out) == out / "multi_turn"
        # Later repetitions of the first experiment: no multi-turn.
        assert runner._multi_turn_dir_for(0, 2, out) is None
        # Other experiments: no multi-turn.
        assert runner._multi_turn_dir_for(1, 1, out) is None

    def test_never_disables_everywhere(self, tmp_path):
        runner = CampaignRunner(_campaign(tmp_path, multi_turn="never"))
        out = tmp_path / "campaign_output"
        assert runner._multi_turn_dir_for(0, 1, out) is None
        assert runner._multi_turn_dir_for(1, 1, out) is None


class TestOverlay:
    def test_overlay_enables_and_redirects_output_dir(self, tmp_path):
        runner = CampaignRunner(_campaign(tmp_path))
        ov = runner._build_config_overlay(
            ExperimentConfig(name="e"), 1,
            multi_turn_output_dir=tmp_path / "campaign_output" / "multi_turn",
        )
        mt = ov["agent/agent_eval"]["agent_eval"]["multi_turn"]
        assert mt["enabled"] is True
        assert mt["output_dir"] == str(tmp_path / "campaign_output" / "multi_turn")

    def test_overlay_disables_multi_turn_for_other_runs(self, tmp_path):
        runner = CampaignRunner(_campaign(tmp_path))
        ov = runner._build_config_overlay(ExperimentConfig(name="e"), 2)
        mt = ov["agent/agent_eval"]["agent_eval"]["multi_turn"]
        assert mt == {"enabled": False}
        # Explicit disable must not leak a stale output_dir from the base yaml.
        assert "output_dir" not in mt


class TestCampaignResultMultiTurn:
    def test_success_status_path_and_metrics(self, tmp_path, monkeypatch):
        campaign = _campaign(tmp_path)
        out_dir = tmp_path / "campaign_output"
        _write_mt_file(out_dir)
        _stub_runs(monkeypatch)

        result = CampaignRunner(campaign).run_campaign()

        mt = result.multi_turn
        assert mt["status"] == "success"
        assert mt["path"].endswith(str(Path("multi_turn") / "multi_turn.json"))
        assert mt["metrics"]["turn_success_rate"] == 0.9
        assert mt["metrics"]["failed_conversations"] == 2
        # Serialized into campaign_result.json
        on_disk = json.loads((out_dir / "campaign_result.json").read_text(encoding="utf-8"))
        assert on_disk["multi_turn"]["status"] == "success"

    def test_multi_turn_metrics_never_enter_comparisons(self, tmp_path, monkeypatch):
        campaign = _campaign(tmp_path)
        _write_mt_file(tmp_path / "campaign_output")
        _stub_runs(monkeypatch)

        result = CampaignRunner(campaign).run_campaign()

        blob = json.dumps(result.comparisons)
        assert "turn_success_rate" not in blob
        assert "conversation_success_rate" not in blob
        assert "multi_turn" not in blob

    def test_not_run_when_first_experiment_failed_early(self, tmp_path, monkeypatch):
        campaign = _campaign(tmp_path)
        _stub_runs(monkeypatch, fail_first=True)

        result = CampaignRunner(campaign).run_campaign()

        assert result.multi_turn["status"] == "not_run"
        assert "failed before multi-turn step" in result.multi_turn["reason"]

    def test_not_run_when_first_succeeded_but_no_file(self, tmp_path, monkeypatch):
        campaign = _campaign(tmp_path)
        _stub_runs(monkeypatch)

        result = CampaignRunner(campaign).run_campaign()

        assert result.multi_turn["status"] == "not_run"
        assert "produced no multi_turn.json" in result.multi_turn["reason"]

    def test_disabled_mode_reports_disabled(self, tmp_path, monkeypatch):
        campaign = _campaign(tmp_path, multi_turn="never")
        _stub_runs(monkeypatch)

        result = CampaignRunner(campaign).run_campaign()

        assert result.multi_turn["status"] == "disabled"

    def test_skipped_no_credentials_status_propagates(self, tmp_path, monkeypatch):
        campaign = _campaign(tmp_path)
        _write_mt_file(tmp_path / "campaign_output", status="skipped_no_credentials")
        _stub_runs(monkeypatch)

        result = CampaignRunner(campaign).run_campaign()

        assert result.multi_turn["status"] == "skipped_no_credentials"
        # Skipped artifacts carry no metrics — must not fabricate any.
        assert result.multi_turn["metrics"] == {}

    def test_result_roundtrip_preserves_multi_turn(self, tmp_path):
        result = CampaignResult(
            campaign_id="c", campaign_hash="h",
            multi_turn={"status": "success", "path": "/x/multi_turn.json", "metrics": {"turn_success_rate": 0.5}},
        )
        restored = CampaignResult.from_dict(result.to_dict())
        assert restored.multi_turn == result.multi_turn


class TestOverlayPassesConfigCheck:
    """Regression for the real-run bug: every key the campaign overlay sets
    must exist in configs/agent/agent_eval.yaml, or _check_overlay_keys
    rejects the whole run before it starts (campaign_id was missing)."""

    def test_real_campaign_overlay_loads_via_config_system(self, tmp_path, monkeypatch):
        runner = CampaignRunner(_campaign(tmp_path))
        experiment = ExperimentConfig(
            name="exp_x",
            agent_config={"agents": ["baseline"]},
            evaluation_config={"per_segment": 3},
            repetition_count=1,
        )
        # The designated multi-turn run AND a regular run — both overlays
        # must survive the fail-closed overlay key check.
        for mt_dir in (tmp_path / "campaign_output" / "multi_turn", None):
            overlay = runner._build_config_overlay(
                experiment, 1, multi_turn_output_dir=mt_dir
            )
            overlay_path = tmp_path / f"overlay_{mt_dir is not None}.yaml"
            overlay_path.write_text(
                yaml.safe_dump(overlay, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            monkeypatch.setenv("CONFIG_OVERLAY_PATH", str(overlay_path))
            cfg = load_config("agent/agent_eval")["agent_eval"]
            assert cfg["campaign_id"] == "mt_campaign"
            assert cfg["agents"] == ["baseline"]
            assert cfg["multi_turn"]["enabled"] is (mt_dir is not None)
