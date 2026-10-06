import pytest

from package.llm.base import LLMProvider
from package.llm.factory import build_llm_provider
from package.llm.providers import OpenAICompatibleProvider


def test_openai_compatible_provider_is_llm_provider_subclass():
    provider = OpenAICompatibleProvider(
        base_url="http://localhost:8000/v1", model="test-model"
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
        }
    )
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.provider_name == "openai_compatible"
