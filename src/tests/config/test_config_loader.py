import pytest

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
    assert llm_config["provider"] in {"mock", "openai_compatible"}
    assert llm_config["model"]
