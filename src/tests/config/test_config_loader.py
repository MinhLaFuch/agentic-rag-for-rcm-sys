import dataclasses
import re
import time

import pytest
import yaml

from package.config import get_data_paths
from package.config._constants import CONFIG_DIR
from package.config.load_config import ConfigError, load_config


def test_data_config_has_domains_and_resource_paths():
    domains_config = load_config("path/domains")
    run_tag_config = load_config("path/run_tag")
    data_paths_config = load_config("path/data_paths")
    cleaning_config = load_config("data/cleaning")
    assert [d["name"] for d in domains_config["domains"]] == ["Video_Games", "Toys_and_Games", "Electronics"]
    assert run_tag_config["tag"] == "multi_domain"
    assert data_paths_config["paths"]["raw_dir"] == "resource/raw"
    assert cleaning_config["cleaning"]["chunk_size"] > 0


def test_env_interpolation_and_missing_env_raises(tmp_path, monkeypatch):
    (tmp_path / "demo.yaml").write_text("root: ${DEMO_ROOT}/raw\n", encoding="utf-8")
    monkeypatch.setenv("DEMO_ROOT", "resource")
    assert load_config("demo", config_dir=tmp_path)["root"] == "resource/raw"
    monkeypatch.delenv("DEMO_ROOT")
    with pytest.raises(ConfigError):
        load_config("demo", config_dir=tmp_path)


def test_load_config_file_not_found():
    with pytest.raises(ConfigError):
        load_config("path/does_not_exist")


def test_llm_config_loads_independently_of_domain():
    # llm.yaml không tham chiếu DOMAIN nên phải load được độc lập
    llm_config = load_config("agent/llm")
    assert llm_config["provider"] == "openai_compatible"
    assert llm_config["model"]


def test_env_interpolation_default_and_shell_semantics(tmp_path, monkeypatch):
    (tmp_path / "demo.yaml").write_text("a: ${DEMO_KEY:-}\nb: ${DEMO_KEY:-fallback}\nc: x-${DEMO_KEY:-y}-z\n", encoding="utf-8")
    monkeypatch.delenv("DEMO_KEY", raising=False)
    assert load_config("demo", config_dir=tmp_path) == {"a": "", "b": "fallback", "c": "x-y-z"}
    monkeypatch.setenv("DEMO_KEY", "")  # set-but-empty counts as unset for ":-", like the shell
    assert load_config("demo", config_dir=tmp_path)["b"] == "fallback"
    monkeypatch.setenv("DEMO_KEY", "real")
    assert load_config("demo", config_dir=tmp_path) == {"a": "real", "b": "real", "c": "x-real-z"}


def test_llm_yaml_holds_no_literal_credential(monkeypatch):
    raw = yaml.safe_load((CONFIG_DIR / "agent/llm.yaml").read_text(encoding="utf-8"))  # un-interpolated, as committed
    assert re.fullmatch(r"\$\{[A-Z][A-Z0-9_]*(:-[^}]*)?\}", raw["api_key"] or "${EMPTY:-}"), (
        "api_key must be an env reference like ${LLM_API_KEY:-}, never a literal secret"
    )
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert load_config("agent/llm")["api_key"] == ""  # no secret required to load the config (local servers, CI)
    monkeypatch.setenv("LLM_API_KEY", "from-env")
    assert load_config("agent/llm")["api_key"] == "from-env"


def test_every_data_paths_key_is_a_datapaths_field_and_vice_versa():
    # keeps data_paths.yaml free of dead keys (a key nobody reads) and DataPaths free of undeclared dirs
    yaml_keys = set(load_config("path/data_paths")["paths"])
    fields = {f.name for f in dataclasses.fields(get_data_paths())} - {"tag"}
    assert yaml_keys == fields


def test_every_data_paths_dir_is_distinct_and_under_project():
    paths = get_data_paths()
    dirs = [getattr(paths, f.name) for f in dataclasses.fields(paths) if f.name != "tag"]
    assert len(set(dirs)) == len(dirs)
    assert all(CONFIG_DIR.parent in d.parents for d in dirs)


def test_config_cache_invalidation_on_file_change(tmp_path, monkeypatch):
    """Test that modifying a config file clears the LRU cache in _limits.py."""
    (tmp_path / "test_config.yaml").write_text("test:\n  value: 10\n", encoding="utf-8")

    # First load
    cfg1 = load_config("test_config", config_dir=tmp_path)
    assert cfg1["test"]["value"] == 10

    # Wait a bit to ensure mtime changes
    time.sleep(0.01)

    # Modify the file
    (tmp_path / "test_config.yaml").write_text("test:\n  value: 20\n", encoding="utf-8")

    # Second load should get the new value
    cfg2 = load_config("test_config", config_dir=tmp_path)
    assert cfg2["test"]["value"] == 20


def test_config_schema_validation(tmp_path):
    """Test that Pydantic schema validation works for agent configs."""
    # Create agent subdirectory
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()

    # Valid config
    (agent_dir / "agent.yaml").write_text(
        "agent:\n  max_steps: 8\n  plan_retries: 1\n  reflect_rounds: 1\n  reflect_error_chars: 300\n"
        "  max_tokens: 2048\n  temperature: 0.0\n  type1:\n    candidate_multiplier: 5\n    min_candidates: 50\n",
        encoding="utf-8",
    )
    cfg = load_config("agent/agent", config_dir=tmp_path)
    assert cfg["agent"]["max_steps"] == 8

    # Invalid config (negative value)
    (agent_dir / "agent.yaml").write_text(
        "agent:\n  max_steps: -1\n  plan_retries: 1\n  reflect_rounds: 1\n  reflect_error_chars: 300\n"
        "  max_tokens: 2048\n  temperature: 0.0\n  type1:\n    candidate_multiplier: 5\n    min_candidates: 50\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="Config validation failed"):
        load_config("agent/agent", config_dir=tmp_path)


def test_config_schema_validation_invalid_language(tmp_path):
    """Test that language validation works."""
    # Create agent subdirectory
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir(exist_ok=True)

    (agent_dir / "agent_eval.yaml").write_text(
        "agent_eval:\n  agents: [baseline]\n  k: 10\n  per_segment: 20\n  n_ambiguous: 6\n"
        "  language: 'fr'\n  price_slack: 1.25\n  price_round_to: 5\n  min_metadata_coverage: 0.5\n"
        "  trajectory_error_chars: 300\n  max_consecutive_llm_errors: 5\n"
        "  experiments_subdir: 'agent_eval'\n  trajectory_file: 'test.jsonl'\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="Config validation failed"):
        load_config("agent/agent_eval", config_dir=tmp_path)

