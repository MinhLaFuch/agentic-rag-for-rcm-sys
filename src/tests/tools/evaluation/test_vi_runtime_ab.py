import pytest
import yaml

from scripts.evaluation.run_vi_runtime_ab import prepare, runtime_environment, check_llm


def test_missing_llm_configuration_fails_before_network(monkeypatch):
    import package.api
    monkeypatch.setattr(package.api, "build_llm_provider", lambda cfg: pytest.fail("unexpected provider call"))
    with pytest.raises(ValueError, match="LLM_BASE_URL"):
        check_llm({"base_url": "", "model": "configured-model"})


def test_llm_health_failure_is_explicit(monkeypatch):
    import package.api
    from types import SimpleNamespace
    monkeypatch.setattr(package.api, "build_llm_provider", lambda cfg: SimpleNamespace(health_check=lambda: False))
    with pytest.raises(RuntimeError, match="before dataset loading"):
        check_llm({"base_url": "http://localhost/v1", "model": "model"})


def test_runtime_environment_keeps_required_audit_overlay(tmp_path, monkeypatch):
    import os
    monkeypatch.setenv("CONFIG_OVERLAY_PATH", "unrelated-overlay")
    overlay = tmp_path / "arm.yaml"
    env = runtime_environment(tmp_path, overlay)
    assert env["CONFIG_OVERLAY_PATH"].split(os.pathsep) == [
        str((tmp_path / "src/configs/profiles/multi_domain_v2_audit_20261030.overlay.yaml").resolve()),
        str(overlay.resolve()),
    ]
    assert env["EVAL_BUNDLE_PROFILE"].endswith("multi_domain_v2_audit_20261030.profile.yaml")
    assert os.environ["CONFIG_OVERLAY_PATH"] == "unrelated-overlay"


def test_paired_runtime_configs_keep_cohort_and_isolate_changes(tmp_path):
    arms = prepare(tmp_path, 20, "realistic")
    configs = [yaml.safe_load(path.read_text(encoding="utf-8")) for _, path in arms]
    for c in configs:
        run = c["agent/agent_eval"]["agent_eval"]
        assert run["language"] == "vi"
        assert run["request_scope"] == "realistic"
        assert run["per_segment"] == 20
        assert c["agent/demo"]["demo"]["fallback_to_bm25"] is False
    assert [c["agent/scoring"]["scoring"]["mode"] for c in configs] == ["baseline", "baseline", "hybrid"]
    assert [c["agent/demo"]["demo"]["retrieval_mode"] for c in configs] == ["bm25", "hybrid", "hybrid"]
    assert prepare(tmp_path, 20, "realistic") == arms
    with pytest.raises(ValueError, match="differs"):
        prepare(tmp_path, 40, "realistic")
