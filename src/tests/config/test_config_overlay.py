"""Tests for CONFIG_OVERLAY_PATH fail-closed merging and cache invalidation."""

import os
from pathlib import Path

import pytest
import yaml

from package.agents import get_agent_limits
from package.config.load_config import ConfigError, load_config


def _write_overlay(tmp_path: Path, doc: dict, name: str = "overlay.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return path


def _use_overlay(monkeypatch, path: Path) -> None:
    monkeypatch.setenv("CONFIG_OVERLAY_PATH", str(path))


def test_valid_overlay_merges(tmp_path, monkeypatch):
    overlay = _write_overlay(tmp_path, {
        "agent/agent_eval": {"agent_eval": {"per_segment": 5}},
    })
    _use_overlay(monkeypatch, overlay)
    assert load_config("agent/agent_eval")["agent_eval"]["per_segment"] == 5
    # Untouched keys keep base values
    assert load_config("agent/agent_eval")["agent_eval"]["k"] == 10


def test_overlay_unknown_config_name_rejected(tmp_path, monkeypatch):
    overlay = _write_overlay(tmp_path, {
        "agent/agent_evl": {"agent_eval": {"per_segment": 5}},
    })
    _use_overlay(monkeypatch, overlay)
    with pytest.raises(ConfigError, match="unknown config"):
        load_config("agent/agent_eval")


def test_overlay_missing_wrapper_key_rejected(tmp_path, monkeypatch):
    # per_segment sits under agent_eval; dropping the wrapper must fail, not no-op
    overlay = _write_overlay(tmp_path, {
        "agent/agent_eval": {"per_segment": 5},
    })
    _use_overlay(monkeypatch, overlay)
    with pytest.raises(ConfigError, match="unknown key"):
        load_config("agent/agent_eval")


def test_overlay_typo_inner_key_rejected(tmp_path, monkeypatch):
    overlay = _write_overlay(tmp_path, {
        "agent/agent_eval": {"agent_eval": {"per_segmnet": 5}},
    })
    _use_overlay(monkeypatch, overlay)
    with pytest.raises(ConfigError, match="per_segmnet"):
        load_config("agent/agent_eval")


def test_overlay_schema_violation_rejected(tmp_path, monkeypatch):
    # Key exists in YAML but fails the Pydantic schema (extra=forbid / validators)
    overlay = _write_overlay(tmp_path, {
        "agent/inference": {"inference": {"mode": "gpt"}},
    })
    _use_overlay(monkeypatch, overlay)
    with pytest.raises(ConfigError):
        load_config("agent/inference")


def test_overlay_missing_file_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("CONFIG_OVERLAY_PATH", str(tmp_path / "nope.yaml"))
    with pytest.raises(ConfigError, match="missing file"):
        load_config("agent/agent_eval")


def test_overlay_not_a_mapping_rejected(tmp_path, monkeypatch):
    path = tmp_path / "overlay.yaml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    _use_overlay(monkeypatch, path)
    with pytest.raises(ConfigError, match="mapping"):
        load_config("agent/agent_eval")


def test_limits_refresh_on_env_set_then_getter(tmp_path, monkeypatch):
    """Setting CONFIG_OVERLAY_PATH then calling a limits getter directly must not be stale."""
    base = get_agent_limits().reflect_rounds
    overlay = _write_overlay(tmp_path, {
        "agent/agent": {"agent": {"reflect_rounds": base + 2}},
    })
    _use_overlay(monkeypatch, overlay)
    assert get_agent_limits().reflect_rounds == base + 2
    monkeypatch.delenv("CONFIG_OVERLAY_PATH")
    assert get_agent_limits().reflect_rounds == base


def test_limits_refresh_on_equal_mtime_swap(tmp_path, monkeypatch):
    """Switching between two overlay files with identical mtimes must not serve stale limits."""
    a = _write_overlay(tmp_path, {"agent/agent": {"agent": {"reflect_rounds": 2}}}, "a.yaml")
    b = _write_overlay(tmp_path, {"agent/agent": {"agent": {"reflect_rounds": 3}}}, "b.yaml")
    # Force identical mtimes — signature must still differ via resolved path
    ts = os.stat(a).st_mtime_ns
    os.utime(b, ns=(ts, ts))

    _use_overlay(monkeypatch, a)
    assert get_agent_limits().reflect_rounds == 2
    _use_overlay(monkeypatch, b)
    assert get_agent_limits().reflect_rounds == 3
