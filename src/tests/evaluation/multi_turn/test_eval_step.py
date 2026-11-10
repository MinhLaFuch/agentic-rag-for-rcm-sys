"""Tests for the multi-turn eval step wired into run_agent_eval / campaign.

The LLM gate is exercised for real (env vars -> configs/agent/llm.yaml
interpolation); only the subprocess itself is stubbed where a "successful"
LLM run is required — no real LLM calls anywhere.
"""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from package.evaluation.multi_turn import _eval_step


@pytest.fixture(autouse=True)
def _no_llm_env(monkeypatch):
    """Guarantee the real _llm_configured gate sees empty credentials."""
    monkeypatch.setenv("LLM_BASE_URL", "")
    monkeypatch.setenv("LLM_API_KEY", "")


def _summary_payload(**overrides):
    payload = {
        "status": "success",
        "multi_turn_version": "test",
        "total_conversations": 11,
        "turn_success_rate": 0.9,
        "conversation_success_rate": 0.8,
        "turn_completion_ratio": 0.95,
        "total_turns_scheduled": 20,
        "total_turns_executed": 19,
        "failed_conversations": 2,
    }
    payload.update(overrides)
    return payload


class TestRunMultiTurnForEvalGate:
    def test_disabled_returns_none(self, tmp_path):
        for block in (None, {}, {"enabled": False}, {"enabled": False, "output_dir": str(tmp_path)}):
            assert _eval_step.run_multi_turn_for_eval(block, tmp_path / "mt.json") is None

    def test_enabled_without_output_dir_uses_default(self, tmp_path):
        info = _eval_step.run_multi_turn_for_eval(
            {"enabled": True}, tmp_path / "exp_001" / "multi_turn.json"
        )
        assert info["status"] == "skipped_no_credentials"
        assert info["output_path"] == str((tmp_path / "exp_001" / "multi_turn.json").resolve())
        assert (tmp_path / "exp_001" / "multi_turn.json").exists()

    def test_enabled_with_output_dir_redirects(self, tmp_path):
        target = tmp_path / "campaign" / "multi_turn"
        info = _eval_step.run_multi_turn_for_eval(
            {"enabled": True, "output_dir": str(target)}, tmp_path / "exp_001" / "multi_turn.json"
        )
        assert info["output_path"] == str((target / "multi_turn.json").resolve())
        # The experiment dir must NOT receive a copy — single location only.
        assert not (tmp_path / "exp_001" / "multi_turn.json").exists()
        payload = json.loads((target / "multi_turn.json").read_text(encoding="utf-8"))
        assert payload["status"] == "skipped_no_credentials"
        assert "reason" in payload


class TestRunMultiTurnEval:
    def test_skipped_no_credentials_writes_explicit_status(self, tmp_path):
        out = tmp_path / "mt.json"
        info = _eval_step.run_multi_turn_eval(dataset="d.jsonl", output_path=out)
        assert info["status"] == "skipped_no_credentials"
        assert info["summary"] is None
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["status"] == "skipped_no_credentials"
        assert payload["dataset"] == "d.jsonl"
        # No fabricated metrics may appear in a skipped artifact.
        assert "turn_success_rate" not in payload

    def test_success_path_parses_summary(self, tmp_path, monkeypatch):
        out = tmp_path / "mt.json"

        def fake_run(cmd, **kwargs):
            output = Path(cmd[cmd.index("--output") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(_summary_payload()), encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="ok", stderr="")

        monkeypatch.setattr(_eval_step.subprocess, "run", fake_run)
        monkeypatch.setattr(_eval_step, "_llm_configured", lambda: True)

        info = _eval_step.run_multi_turn_eval(dataset="d.jsonl", output_path=out)
        assert info["status"] == "success"
        assert info["resumed"] is False
        assert info["summary"]["turn_success_rate"] == 0.9

    def test_failed_subprocess_writes_failed_status(self, tmp_path, monkeypatch):
        out = tmp_path / "mt.json"

        def fake_run(cmd, **kwargs):
            return SimpleNamespace(returncode=1, stdout="", stderr="boom: no provider")

        monkeypatch.setattr(_eval_step.subprocess, "run", fake_run)
        monkeypatch.setattr(_eval_step, "_llm_configured", lambda: True)

        info = _eval_step.run_multi_turn_eval(dataset="d.jsonl", output_path=out)
        assert info["status"] == "failed"
        assert "boom" in info["error"]
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["status"] == "failed"

    def test_resume_returns_existing_success_without_subprocess(self, tmp_path, monkeypatch):
        out = tmp_path / "mt.json"
        out.write_text(json.dumps(_summary_payload()), encoding="utf-8")

        def _explode(*a, **k):
            raise AssertionError("subprocess must not run on resume")

        monkeypatch.setattr(_eval_step.subprocess, "run", _explode)
        # Note: no _llm_configured patch — resume must short-circuit even
        # when credentials are absent.
        info = _eval_step.run_multi_turn_eval(dataset="d.jsonl", output_path=out)
        assert info["status"] == "success"
        assert info["resumed"] is True

    def test_relative_output_dir_resolves_under_experiments(self, tmp_path, monkeypatch):
        fake_paths = SimpleNamespace(experiments_dir=tmp_path / "experiments", src_root=tmp_path)
        monkeypatch.setattr(_eval_step, "get_data_paths", lambda: fake_paths)
        info = _eval_step.run_multi_turn_eval(
            dataset="d.jsonl", output_path="agent_eval/campaigns/c1/multi_turn/multi_turn.json"
        )
        expected = tmp_path / "experiments" / "agent_eval" / "campaigns" / "c1" / "multi_turn" / "multi_turn.json"
        assert info["output_path"] == str(expected.resolve())
        assert expected.exists()


class TestExtractMultiTurnMetrics:
    def test_extracts_only_known_metric_keys(self):
        metrics = _eval_step.extract_multi_turn_metrics(_summary_payload(extra="x"))
        assert metrics["turn_success_rate"] == 0.9
        assert metrics["failed_conversations"] == 2
        assert "extra" not in metrics
        assert "status" not in metrics

    def test_none_and_non_dict_safe(self):
        assert _eval_step.extract_multi_turn_metrics(None) == {}
        assert _eval_step.extract_multi_turn_metrics("junk") == {}
