import os

import pytest

from src.config.loader import ConfigError, load_config


def test_load_config_with_domain_env(monkeypatch):
    monkeypatch.setenv("DOMAIN", "Video_Games")
    config = load_config("data")
    assert config["domain"] == "Video_Games"
    assert config["raw_review_config"] == "raw_review_Video_Games"
    assert config["paths"]["raw_dir"] == "data/raw/Video_Games"


def test_load_config_missing_env_raises(monkeypatch):
    monkeypatch.delenv("DOMAIN", raising=False)
    with pytest.raises(ConfigError):
        load_config("data")


def test_load_config_file_not_found():
    with pytest.raises(ConfigError):
        load_config("does_not_exist")


def test_agent_config_does_not_require_domain():
    # agent.yaml không tham chiếu DOMAIN nên phải load được độc lập
    config = load_config("agent")
    assert config["llm"]["provider"] == "mock"
    assert config["reranking"]["input_top_k"] == 20
    assert config["multi_agent"]["enabled"] is False


def test_evaluation_config_has_experiment_matrix():
    config = load_config("evaluation")
    assert "E9_full_system" in config["experiment_matrix"]
    assert len(config["experiment_matrix"]) == 10
