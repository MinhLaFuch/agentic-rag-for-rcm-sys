"""
Integration test for config cache invalidation during resume.

This test ensures that when a config file is modified between runs,
the LRU cache is cleared and the new config values are used.
"""

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from package.config.load_config import load_config, ConfigError, _file_mtime_cache


def test_resume_with_modified_config_clears_cache(tmp_path):
    """
    Test that modifying a config file between runs clears the LRU cache.
    This simulates the scenario where a user edits configs/agent/agent.yaml
    and then re-runs with --resume.
    """
    # Clear cache to avoid interference from other tests
    _file_mtime_cache.clear()

    agent_dir = tmp_path / "configs" / "agent"
    agent_dir.mkdir(parents=True)

    # Create initial config
    (agent_dir / "agent.yaml").write_text(
        "agent:\n  max_steps: 8\n  plan_retries: 1\n  reflect_rounds: 1\n  reflect_error_chars: 300\n"
        "  max_tokens: 2048\n  temperature: 0.0\n  type1:\n    candidate_multiplier: 5\n    min_candidates: 50\n",
        encoding="utf-8",
    )

    # First load
    cfg1 = load_config("agent/agent", config_dir=tmp_path / "configs")
    assert cfg1["agent"]["max_steps"] == 8
    assert cfg1["agent"]["type1"]["candidate_multiplier"] == 5

    # Wait to ensure mtime changes
    time.sleep(0.01)

    # Modify config
    (agent_dir / "agent.yaml").write_text(
        "agent:\n  max_steps: 16\n  plan_retries: 2\n  reflect_rounds: 2\n  reflect_error_chars: 500\n"
        "  max_tokens: 4096\n  temperature: 0.1\n  type1:\n    candidate_multiplier: 10\n    min_candidates: 100\n",
        encoding="utf-8",
    )

    # Second load should get new values
    cfg2 = load_config("agent/agent", config_dir=tmp_path / "configs")
    assert cfg2["agent"]["max_steps"] == 16
    assert cfg2["agent"]["type1"]["candidate_multiplier"] == 10


def test_resume_invalid_config_rejected(tmp_path):
    """
    Test that if a config file is modified to an invalid state,
    loading it raises ConfigError.
    """
    # Clear cache to avoid interference from other tests
    _file_mtime_cache.clear()

    agent_dir = tmp_path / "configs" / "agent"
    agent_dir.mkdir(parents=True)

    # Create valid initial config
    (agent_dir / "agent.yaml").write_text(
        "agent:\n  max_steps: 8\n  plan_retries: 1\n  reflect_rounds: 1\n  reflect_error_chars: 300\n"
        "  max_tokens: 2048\n  temperature: 0.0\n  type1:\n    candidate_multiplier: 5\n    min_candidates: 50\n",
        encoding="utf-8",
    )

    # First load succeeds
    cfg1 = load_config("agent/agent", config_dir=tmp_path / "configs")
    assert cfg1["agent"]["max_steps"] == 8

    # Wait to ensure mtime changes
    time.sleep(0.01)

    # Modify to invalid config (temperature out of range)
    (agent_dir / "agent.yaml").write_text(
        "agent:\n  max_steps: 8\n  plan_retries: 1\n  reflect_rounds: 1\n  reflect_error_chars: 300\n"
        "  max_tokens: 2048\n  temperature: 3.0\n  type1:\n    candidate_multiplier: 5\n    min_candidates: 50\n",
        encoding="utf-8",
    )

    # Second load should fail validation
    with pytest.raises(ConfigError, match="Config validation failed"):
        load_config("agent/agent", config_dir=tmp_path / "configs")


def test_multiple_config_files_cache_invalidation(tmp_path):
    """
    Test that modifying multiple config files clears their respective caches.
    """
    # Clear cache to avoid interference from other tests
    _file_mtime_cache.clear()

    agent_dir = tmp_path / "configs" / "agent"
    agent_dir.mkdir(parents=True)

    # Create multiple configs
    (agent_dir / "agent.yaml").write_text(
        "agent:\n  max_steps: 8\n  plan_retries: 1\n  reflect_rounds: 1\n  reflect_error_chars: 300\n"
        "  max_tokens: 2048\n  temperature: 0.0\n  type1:\n    candidate_multiplier: 5\n    min_candidates: 50\n",
        encoding="utf-8",
    )

    (agent_dir / "tools.yaml").write_text(
        "tools:\n  max_candidates: 1000\n  max_query_rows: 100\n  sql_time_budget_seconds: 5.0\n"
        "  max_output_summary_chars: 500\n  defaults:\n    sql_limit: 100\n    item_cf_top_k: 20\n"
        "    query_max_rows: 20\n    memory_top_n_categories: 3\n    memory_recent_items: 5\n"
        "  semantic_search:\n    default_limit: 50\n    max_query_tokens: 20\n",
        encoding="utf-8",
    )

    # Load both configs
    cfg_agent1 = load_config("agent/agent", config_dir=tmp_path / "configs")
    cfg_tools1 = load_config("agent/tools", config_dir=tmp_path / "configs")
    assert cfg_agent1["agent"]["max_steps"] == 8
    assert cfg_tools1["tools"]["max_candidates"] == 1000

    # Wait to ensure mtime changes
    time.sleep(0.01)

    # Modify only agent.yaml
    (agent_dir / "agent.yaml").write_text(
        "agent:\n  max_steps: 16\n  plan_retries: 1\n  reflect_rounds: 1\n  reflect_error_chars: 300\n"
        "  max_tokens: 2048\n  temperature: 0.0\n  type1:\n    candidate_multiplier: 5\n    min_candidates: 50\n",
        encoding="utf-8",
    )

    # agent.yaml should be reloaded, tools.yaml should stay cached
    cfg_agent2 = load_config("agent/agent", config_dir=tmp_path / "configs")
    cfg_tools2 = load_config("agent/tools", config_dir=tmp_path / "configs")
    assert cfg_agent2["agent"]["max_steps"] == 16  # New value
    assert cfg_tools2["tools"]["max_candidates"] == 1000  # Cached value


def test_config_with_env_var_interpolation_and_validation(tmp_path, monkeypatch):
    """
    Test that env var interpolation works together with schema validation.
    """
    # Clear cache to avoid interference from other tests
    _file_mtime_cache.clear()

    agent_dir = tmp_path / "configs" / "agent"
    agent_dir.mkdir(parents=True)

    # Config with env var
    monkeypatch.setenv("TEST_STEPS", "12")
    (agent_dir / "agent.yaml").write_text(
        "agent:\n  max_steps: ${TEST_STEPS}\n  plan_retries: 1\n  reflect_rounds: 1\n  reflect_error_chars: 300\n"
        "  max_tokens: 2048\n  temperature: 0.0\n  type1:\n    candidate_multiplier: 5\n    min_candidates: 50\n",
        encoding="utf-8",
    )

    cfg = load_config("agent/agent", config_dir=tmp_path / "configs")
    assert cfg["agent"]["max_steps"] == 12

    # Change env var to invalid value
    monkeypatch.setenv("TEST_STEPS", "-5")
    # Reload should fail validation
    with pytest.raises(ConfigError, match="Config validation failed"):
        load_config("agent/agent", config_dir=tmp_path / "configs")
