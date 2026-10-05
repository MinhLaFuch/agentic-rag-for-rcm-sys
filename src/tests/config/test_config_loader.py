import dataclasses
import re

import pytest
import yaml

from package.config import get_data_paths
from package.config._constants import CONFIG_DIR
from package.config.loader import ConfigError, load_config


def test_data_config_has_domains_and_resource_paths():
    domains_config = load_config("domains")
    run_tag_config = load_config("run_tag")
    data_paths_config = load_config("data_paths")
    cleaning_config = load_config("cleaning")
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
        load_config("does_not_exist")


def test_llm_config_loads_independently_of_domain():
    # llm.yaml không tham chiếu DOMAIN nên phải load được độc lập
    llm_config = load_config("llm")
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
    raw = yaml.safe_load((CONFIG_DIR / "llm.yaml").read_text(encoding="utf-8"))  # un-interpolated, as committed
    assert re.fullmatch(r"\$\{[A-Z][A-Z0-9_]*(:-[^}]*)?\}", raw["api_key"] or "${EMPTY:-}"), (
        "api_key must be an env reference like ${LLM_API_KEY:-}, never a literal secret"
    )
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert load_config("llm")["api_key"] == ""  # no secret required to load the config (local servers, CI)
    monkeypatch.setenv("LLM_API_KEY", "from-env")
    assert load_config("llm")["api_key"] == "from-env"


def test_every_data_paths_key_is_a_datapaths_field_and_vice_versa():
    # keeps data_paths.yaml free of dead keys (a key nobody reads) and DataPaths free of undeclared dirs
    yaml_keys = set(load_config("data_paths")["paths"])
    fields = {f.name for f in dataclasses.fields(get_data_paths())} - {"tag"}
    assert yaml_keys == fields


def test_every_data_paths_dir_is_distinct_and_under_project():
    paths = get_data_paths()
    dirs = [getattr(paths, f.name) for f in dataclasses.fields(paths) if f.name != "tag"]
    assert len(set(dirs)) == len(dirs)
    assert all(CONFIG_DIR.parent in d.parents for d in dirs)

