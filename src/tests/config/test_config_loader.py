import pytest

from package.config.loader import ConfigError, load_config


def test_data_config_has_domains_and_resource_paths():
    config = load_config("data")
    assert [d["name"] for d in config["domains"]] == ["Video_Games", "Toys_and_Games", "Electronics"]
    assert config["run_tag"] == "multi_domain"
    assert config["paths"]["raw_dir"] == "resource/raw"
    assert config["cleaning"]["chunk_size"] > 0


def test_env_interpolation_and_missing_env_raises(tmp_path, monkeypatch):
    (tmp_path / "demo.yaml").write_text("root: ${DEMO_ROOT}/raw\n", encoding="utf-8")
    monkeypatch.setenv("DEMO_ROOT", "resource")
    assert load_config("demo", config_dir=tmp_path)["root"] == "resource/raw"
    monkeypatch.delenv("DEMO_ROOT")
    with pytest.raises(ConfigError):
        load_config("demo", config_dir=tmp_path)


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
