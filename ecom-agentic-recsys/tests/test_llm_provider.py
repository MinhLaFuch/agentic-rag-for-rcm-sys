import json

import pytest

from src.llm.base import LLMMessage, LLMProvider
from src.llm.factory import build_llm_provider
from src.llm.providers.mock import MockLLMProvider


def test_mock_provider_is_llm_provider_subclass():
    provider = MockLLMProvider()
    assert isinstance(provider, LLMProvider)
    assert provider.health_check() is True


def test_mock_provider_echoes_user_message():
    provider = MockLLMProvider()
    response = provider.complete(
        [
            LLMMessage(role="system", content="you are a helpful assistant"),
            LLMMessage(role="user", content="recommend me a laptop"),
        ]
    )
    assert "recommend me a laptop" in response.text
    assert response.provider_name == "mock"
    assert response.latency_seconds is not None


def test_mock_provider_json_mode_returns_valid_json():
    provider = MockLLMProvider()
    response = provider.complete(
        [LLMMessage(role="user", content="rerank these items")],
        response_format_json=True,
    )
    parsed = json.loads(response.text)
    assert "item_id" in parsed
    assert "score" in parsed
    assert "reasons" in parsed
    assert isinstance(parsed["reasons"], list)


def test_factory_builds_mock_provider_by_default():
    provider = build_llm_provider({"llm": {"provider": "mock"}})
    assert isinstance(provider, MockLLMProvider)


def test_factory_rejects_unknown_provider():
    with pytest.raises(ValueError):
        build_llm_provider({"llm": {"provider": "not_a_real_provider"}})


def test_factory_requires_base_url_and_model_for_openai_compatible():
    with pytest.raises(ValueError):
        build_llm_provider({"llm": {"provider": "openai_compatible"}})
