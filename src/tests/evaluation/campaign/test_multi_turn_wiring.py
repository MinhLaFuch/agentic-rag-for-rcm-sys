"""Tests for campaign-level multi-turn wiring.

Multi-turn is a per-experiment opt-in (``agent_config.multi_turn``, bool or
dict) capped by the campaign policy ``multi_turn: once|never|all``. Enabled
runs write ``<campaign>/multi_turn/<exp>_run<N>/multi_turn.json`` — never
into an exp_dir — and campaign_result.json.multi_turn reports per-run
statuses. Metrics never enter paired comparisons.
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


def _campaign(
    tmp_path: Path,
    *,
    multi_turn: str = "once",
    repetitions: int = 1,
    agent_multi_turn=None,
) -> CampaignConfig:
    ac = {"agents": ["baseline"]}
    if agent_multi_turn is not None:
        ac["multi_turn"] = agent_multi_turn
    return CampaignConfig(
        campaign_id="mt_campaign",
        dataset={"path": "data/test.jsonl"},
        experiments=[
            ExperimentConfig(name="exp_first", agent_config=dict(ac), repetition_count=repetitions),
            ExperimentConfig(name="exp_second", repetition_count=1),
        ],
        output_dir=str(tmp_path / "campaign_output"),
        comparison_pairs=[("exp_first", "exp_second")],
        multi_turn=multi_turn,
    )


def _stub_runs(monkeypatch, fail_first: bool = False, mt_statuses: dict | None = None):
    """Stub _run_experiment; writes a config_overlay.yaml like the real one and,
    for enabled runs, the multi_turn.json artifact at the overlay's output_dir."""
    mt_statuses = mt_statuses or {}

    def fake_run(self, experiment, run_number, output_dir, multi_turn=None):
        run_dir = output_dir / experiment.name / f"run_{run_number}"
        run_dir.mkdir(parents=True, exist_ok=True)
        frag = multi_turn if multi_turn is not None else {"enabled": False}
        (run_dir / "config_overlay.yaml").write_text(
            yaml.safe_dump(
                {"agent/agent_eval": {"agent_eval": {"multi_turn": frag}}},
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        success = not (fail_first and experiment.name == "exp_first" and run_number == 1)
        key = (experiment.name, run_number)
        # A failed run never reaches the multi-turn step -> no artifact, unless
        # the test explicitly asks for one anyway.
        if frag.get("enabled") and frag.get("output_dir") and (success or key in mt_statuses):
            status = mt_statuses.get(key, "success")
            _write_mt_file(Path(frag["output_dir"]), status)
        return ExperimentRun(
            experiment_name=experiment.name,
            run_number=run_number,
            output_dir=str(run_dir),
            success=success,
            error=None if success else "simulated early failure",
            metrics={"task_success_rate": 0.8},
        )

    monkeypatch.setattr(CampaignRunner, "_run_experiment", fake_run)


def _write_mt_file(output_dir: Path, status: str = "success") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
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
    path = output_dir / "multi_turn.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class TestNormalizeMultiTurnParam:
    def test_bool_and_absent(self):
        n = CampaignRunner._normalize_multi_turn_param
        assert n(None) == {"enabled": False}
        assert n(False) == {"enabled": False}
        assert n(True) == {"enabled": True}

    def test_dict_passthrough_and_enabled_default(self):
        n = CampaignRunner._normalize_multi_turn_param
        assert n({"limits": {"max_turns": 3}}) == {
            "enabled": True, "limits": {"max_turns": 3}
        }
        assert n({"enabled": False, "limits": {}}) == {"enabled": False}

    def test_dict_rejects_output_dir_and_unknown_keys(self):
        n = CampaignRunner._normalize_multi_turn_param
        with pytest.raises(ValueError, match="output_dir"):
            n({"output_dir": "/tmp/x"})
        with pytest.raises(ValueError, match="unmapped keys"):
            n({"bogus": 1})
        with pytest.raises(ValueError, match="bool or dict"):
            n("yes")


class TestMultiTurnPlans:
    def test_never_disables_everywhere(self, tmp_path):
        runner = CampaignRunner(_campaign(tmp_path, multi_turn="never"))
        assert runner._multi_turn_plans(runner.config.expand_parameter_grid(), tmp_path / "out") == {}

    def test_once_without_optin_keeps_legacy_first_run(self, tmp_path):
        """No agent_config.multi_turn anywhere -> experiment[0] run 1 still runs it."""
        runner = CampaignRunner(_campaign(tmp_path))
        experiments = runner.config.expand_parameter_grid()
        plans = runner._multi_turn_plans(experiments, tmp_path / "out")
        assert set(plans) == {(0, 1)}
        frag = plans[(0, 1)]
        assert frag["enabled"] is True
        assert frag["output_dir"].endswith(str(Path("multi_turn") / "exp_first_run1"))

    def test_once_picks_first_optin_run_only(self, tmp_path):
        runner = CampaignRunner(
            _campaign(tmp_path, agent_multi_turn=True, repetitions=2)
        )
        experiments = runner.config.expand_parameter_grid()
        plans = runner._multi_turn_plans(experiments, tmp_path / "out")
        # exp_first opts in but 'once' caps at its first repetition.
        assert set(plans) == {(0, 1)}

    def test_once_optin_on_later_experiment(self, tmp_path):
        campaign = _campaign(tmp_path)
        campaign.experiments[1].agent_config["multi_turn"] = True
        runner = CampaignRunner(campaign)
        experiments = runner.config.expand_parameter_grid()
        plans = runner._multi_turn_plans(experiments, tmp_path / "out")
        assert set(plans) == {(1, 1)}

    def test_all_runs_every_optin(self, tmp_path):
        runner = CampaignRunner(
            _campaign(tmp_path, multi_turn="all", agent_multi_turn=True, repetitions=2)
        )
        experiments = runner.config.expand_parameter_grid()
        plans = runner._multi_turn_plans(experiments, tmp_path / "out")
        assert set(plans) == {(0, 1), (0, 2)}

    def test_never_overrides_optin(self, tmp_path):
        runner = CampaignRunner(
            _campaign(tmp_path, multi_turn="never", agent_multi_turn=True)
        )
        experiments = runner.config.expand_parameter_grid()
        assert runner._multi_turn_plans(experiments, tmp_path / "out") == {}

    def test_param_dict_reaches_plan(self, tmp_path):
        runner = CampaignRunner(
            _campaign(tmp_path, multi_turn="all",
                      agent_multi_turn={"limits": {"max_turns": 4}, "timeout_seconds": 60})
        )
        experiments = runner.config.expand_parameter_grid()
        frag = runner._multi_turn_plans(experiments, tmp_path / "out")[(0, 1)]
        assert frag["limits"] == {"max_turns": 4}
        assert frag["timeout_seconds"] == 60
        assert frag["enabled"] is True


class TestOverlay:
    def test_overlay_enables_and_redirects_output_dir(self, tmp_path):
        runner = CampaignRunner(_campaign(tmp_path))
        frag = {"enabled": True, "output_dir": str(tmp_path / "mt_run")}
        ov = runner._build_config_overlay(ExperimentConfig(name="e"), 1, multi_turn=frag)
        mt = ov["agent/agent_eval"]["agent_eval"]["multi_turn"]
        assert mt == frag

    def test_overlay_param_keys_reach_agent_eval(self, tmp_path):
        runner = CampaignRunner(_campaign(tmp_path))
        frag = {"enabled": True, "limits": {"max_turns": 2}, "output_dir": "/x"}
        ov = runner._build_config_overlay(ExperimentConfig(name="e"), 1, multi_turn=frag)
        mt = ov["agent/agent_eval"]["agent_eval"]["multi_turn"]
        assert mt["limits"] == {"max_turns": 2}
        assert mt["output_dir"] == "/x"

    def test_overlay_disables_multi_turn_by_default(self, tmp_path):
        runner = CampaignRunner(_campaign(tmp_path))
        ov = runner._build_config_overlay(ExperimentConfig(name="e"), 2)
        mt = ov["agent/agent_eval"]["agent_eval"]["multi_turn"]
        assert mt == {"enabled": False}


class TestCampaignResultMultiTurn:
    def test_success_status_runs_and_metrics(self, tmp_path, monkeypatch):
        campaign = _campaign(tmp_path)
        out_dir = tmp_path / "campaign_output"
        _stub_runs(monkeypatch)

        result = CampaignRunner(campaign).run_campaign()

        mt = result.multi_turn
        assert mt["status"] == "success"
        assert mt["mode"] == "once"
        assert len(mt["runs"]) == 1
        entry = mt["runs"][0]
        assert entry["experiment"] == "exp_first" and entry["run_number"] == 1
        assert entry["status"] == "success"
        assert entry["metrics"]["turn_success_rate"] == 0.9
        assert "exp_first_run1" in entry["path"]
        on_disk = json.loads((out_dir / "campaign_result.json").read_text(encoding="utf-8"))
        assert on_disk["multi_turn"]["status"] == "success"

    def test_all_mode_reports_every_optin_run(self, tmp_path, monkeypatch):
        campaign = _campaign(tmp_path, multi_turn="all", agent_multi_turn=True, repetitions=2)
        _stub_runs(monkeypatch)

        result = CampaignRunner(campaign).run_campaign()

        assert result.multi_turn["status"] == "success"
        assert {(e["experiment"], e["run_number"]) for e in result.multi_turn["runs"]} == {
            ("exp_first", 1), ("exp_first", 2)
        }

    def test_partial_when_statuses_differ(self, tmp_path, monkeypatch):
        campaign = _campaign(tmp_path, multi_turn="all", agent_multi_turn=True, repetitions=2)
        _stub_runs(monkeypatch, mt_statuses={("exp_first", 2): "skipped_no_credentials"})

        result = CampaignRunner(campaign).run_campaign()

        assert result.multi_turn["status"] == "partial"
        statuses = {e["run_number"]: e["status"] for e in result.multi_turn["runs"]}
        assert statuses == {1: "success", 2: "skipped_no_credentials"}

    def test_multi_turn_metrics_never_enter_comparisons(self, tmp_path, monkeypatch):
        campaign = _campaign(tmp_path)
        _stub_runs(monkeypatch)

        result = CampaignRunner(campaign).run_campaign()

        blob = json.dumps(result.comparisons)
        assert "turn_success_rate" not in blob
        assert "conversation_success_rate" not in blob
        assert "multi_turn" not in blob

    def test_not_run_when_enabled_run_failed_early(self, tmp_path, monkeypatch):
        campaign = _campaign(tmp_path)
        _stub_runs(monkeypatch, fail_first=True, mt_statuses={})

        result = CampaignRunner(campaign).run_campaign()

        entry = result.multi_turn["runs"][0]
        assert entry["status"] == "not_run"
        assert "failed before multi-turn step" in entry["reason"]
        assert result.multi_turn["status"] == "not_run"

    def test_not_run_when_run_succeeded_but_no_file(self, tmp_path, monkeypatch):
        campaign = _campaign(tmp_path)
        # Enabled run (legacy fallback) but no artifact written: simulate by
        # making the stub skip file creation for this run.
        def fake_run(self, experiment, run_number, output_dir, multi_turn=None):
            run_dir = output_dir / experiment.name / f"run_{run_number}"
            run_dir.mkdir(parents=True, exist_ok=True)
            frag = multi_turn if multi_turn is not None else {"enabled": False}
            (run_dir / "config_overlay.yaml").write_text(
                yaml.safe_dump({"agent/agent_eval": {"agent_eval": {"multi_turn": frag}}}),
                encoding="utf-8",
            )
            return ExperimentRun(
                experiment_name=experiment.name, run_number=run_number,
                output_dir=str(run_dir), success=True, metrics={},
            )
        monkeypatch.setattr(CampaignRunner, "_run_experiment", fake_run)

        result = CampaignRunner(campaign).run_campaign()

        entry = result.multi_turn["runs"][0]
        assert entry["status"] == "not_run"
        assert "produced no multi_turn.json" in entry["reason"]

    def test_disabled_mode_reports_disabled(self, tmp_path, monkeypatch):
        campaign = _campaign(tmp_path, multi_turn="never")
        _stub_runs(monkeypatch)

        result = CampaignRunner(campaign).run_campaign()

        assert result.multi_turn["status"] == "disabled"
        assert result.multi_turn["runs"] == []

    def test_no_optin_and_never_run_has_empty_runs(self, tmp_path, monkeypatch):
        """Stub that writes no overlay at all -> collector finds nothing enabled."""
        def fake_run(self, experiment, run_number, output_dir, multi_turn=None):
            return ExperimentRun(
                experiment_name=experiment.name, run_number=run_number,
                output_dir=str(output_dir / experiment.name / f"run_{run_number}"),
                success=True, metrics={},
            )
        monkeypatch.setattr(CampaignRunner, "_run_experiment", fake_run)

        result = CampaignRunner(_campaign(tmp_path)).run_campaign()

        assert result.multi_turn["status"] == "not_run"
        assert result.multi_turn["runs"] == []

    def test_skipped_no_credentials_status_propagates(self, tmp_path, monkeypatch):
        campaign = _campaign(tmp_path)
        _stub_runs(monkeypatch, mt_statuses={("exp_first", 1): "skipped_no_credentials"})

        result = CampaignRunner(campaign).run_campaign()

        assert result.multi_turn["status"] == "skipped_no_credentials"
        assert result.multi_turn["runs"][0]["metrics"] == {}

    def test_result_roundtrip_preserves_multi_turn(self, tmp_path):
        result = CampaignResult(
            campaign_id="c", campaign_hash="h",
            multi_turn={"status": "success", "mode": "all",
                        "runs": [{"experiment": "e", "run_number": 1,
                                  "status": "success", "path": "/x/multi_turn.json",
                                  "metrics": {"turn_success_rate": 0.5}}]},
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
            agent_config={"agents": ["baseline"], "multi_turn": {"timeout_seconds": 60}},
            evaluation_config={"per_segment": 3},
            repetition_count=1,
        )
        output_dir = tmp_path / "campaign_output"
        plans = runner._multi_turn_plans([experiment], output_dir)
        # Both an enabled run (param dict opt-in under "all") and a disabled
        # run must survive the fail-closed overlay key check.
        for frag in (plans[(0, 1)], None):
            overlay = runner._build_config_overlay(experiment, 1, multi_turn=frag)
            overlay_path = tmp_path / f"overlay_{frag is not None}.yaml"
            overlay_path.write_text(
                yaml.safe_dump(overlay, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            monkeypatch.setenv("CONFIG_OVERLAY_PATH", str(overlay_path))
            cfg = load_config("agent/agent_eval")["agent_eval"]
            assert cfg["campaign_id"] == "mt_campaign"
            assert cfg["agents"] == ["baseline"]
            assert cfg["multi_turn"]["enabled"] is (frag is not None)
            if frag is not None:
                assert cfg["multi_turn"]["timeout_seconds"] == 60
                assert cfg["multi_turn"]["output_dir"].endswith("exp_x_run1")
