import pytest

from package.api.llm_provider import LLMProvider
from package.api.build_llm_provider import build_llm_provider
from package.api import OpenAICompatibleProvider


def test_openai_compatible_provider_is_llm_provider_subclass():
    provider = OpenAICompatibleProvider(
        base_url="http://localhost:8000/v1", model="test-model", timeout_seconds=5.0
    )
    assert isinstance(provider, LLMProvider)
    assert provider.provider_name == "openai_compatible"


def test_factory_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        build_llm_provider({"provider": "not_a_real_provider"})


def test_factory_requires_base_url_and_model_for_openai_compatible():
    with pytest.raises(ValueError):
        build_llm_provider({"provider": "openai_compatible"})


def test_factory_builds_openai_compatible_provider():
    provider = build_llm_provider(
        {
            "provider": "openai_compatible",
            "base_url": "http://localhost:8000/v1",
            "model": "test-model",
            "timeout_seconds": 5.0,
        }
    )
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.provider_name == "openai_compatible"
