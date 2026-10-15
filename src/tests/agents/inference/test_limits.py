"""inference.yaml is loaded and validated like agent.yaml: bad or missing values raise ConfigError."""

import pytest

from package.config.loader import ConfigError, load_config
from package.inference import _limits


@pytest.fixture
def fresh_limits():
    _limits.get_inference_limits.cache_clear()
    yield
    _limits.get_inference_limits.cache_clear()


def test_limits_come_from_inference_yaml():
    cfg = load_config("agent/inference")["inference"]
    limits = _limits.get_inference_limits()
    assert limits.mode == cfg["mode"] and limits.max_items == cfg["max_items"]
    assert limits.max_tokens == cfg["max_tokens"] and limits.temperature == cfg["temperature"]
    assert limits.llm_retries == cfg["llm_retries"]
    assert limits.check_numbers == cfg["check_numbers"] and limits.price_tolerance == cfg["price_tolerance"]


@pytest.mark.parametrize(
    "patch",
    [
        {"mode": "gpt"}, {"mode": None},
        {"max_items": 0}, {"max_items": -3},
        {"max_tokens": 0},
        {"temperature": -0.1},
        {"llm_retries": -1},
        {"price_tolerance": -0.5},
        {"check_numbers": "yes"},
    ],
)
def test_invalid_values_are_rejected(monkeypatch, fresh_limits, patch):
    bad = {"inference": {**load_config("agent/inference")["inference"], **patch}}
    monkeypatch.setattr(_limits, "load_config", lambda name: bad)
    with pytest.raises(ConfigError):
        _limits.get_inference_limits()


@pytest.mark.parametrize("key", ["mode", "max_items", "max_tokens", "temperature", "llm_retries", "check_numbers", "price_tolerance"])
def test_missing_key_is_a_config_error(monkeypatch, fresh_limits, key):
    cfg = dict(load_config("agent/inference")["inference"])
    del cfg[key]
    monkeypatch.setattr(_limits, "load_config", lambda name: {"inference": cfg})
    with pytest.raises(ConfigError):
        _limits.get_inference_limits()


def test_missing_section_is_a_config_error(monkeypatch, fresh_limits):
    monkeypatch.setattr(_limits, "load_config", lambda name: {})
    with pytest.raises(ConfigError):
        _limits.get_inference_limits()
