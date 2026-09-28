from __future__ import annotations

from typing import Any

from src.llm.base import LLMProvider
from src.llm.providers.mock import MockLLMProvider
from src.llm.providers.openai_compatible import OpenAICompatibleProvider

_SUPPORTED_PROVIDERS = {"mock", "openai_compatible"}


def build_llm_provider(config: dict[str, Any]) -> LLMProvider:
    """
    config kỳ vọng có dạng (xem configs/agent.yaml):
        llm:
          provider: mock | openai_compatible
          model: <model name>
          base_url: <chỉ cần cho openai_compatible>
          api_key: <chỉ cần cho openai_compatible, có thể để trống với local server>
    """
    llm_config = config.get("llm", {})
    provider_name = llm_config.get("provider", "mock")

    if provider_name not in _SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unknown LLM provider '{provider_name}'. "
            f"Supported: {sorted(_SUPPORTED_PROVIDERS)}"
        )

    if provider_name == "mock":
        return MockLLMProvider()

    if provider_name == "openai_compatible":
        base_url = llm_config.get("base_url")
        model = llm_config.get("model")
        if not base_url or not model:
            raise ValueError(
                "openai_compatible provider requires 'base_url' and 'model' in config"
            )
        return OpenAICompatibleProvider(
            base_url=base_url,
            model=model,
            api_key=llm_config.get("api_key"),
            timeout_seconds=llm_config.get("timeout_seconds", 30.0),
        )

    raise AssertionError("unreachable")
