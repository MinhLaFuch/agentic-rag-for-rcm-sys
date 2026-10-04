"""
Factory tạo LLMProvider từ config (mục XX, XXI).

Agent/tool code chỉ nên gọi `build_llm_provider(config)`, không tự
`import` provider cụ thể. Điều này giữ đúng nguyên tắc: business logic
không phụ thuộc trực tiếp vào một provider.
"""

from __future__ import annotations

from typing import Any

from .base import LLMProvider
from .providers.mock import MockLLMProvider
from .providers.openai_compatible import OpenAICompatibleProvider

from ._config import SUPPORTED_PROVIDERS


def build_llm_provider(config: dict[str, Any]) -> LLMProvider:
    """
    config kỳ vọng có dạng (xem configs/llm.yaml):
        provider: mock | openai_compatible
        model: <model name>
        base_url: <chỉ cần cho openai_compatible>
        api_key: <chỉ cần cho openai_compatible, có thể để trống với local server>
    """
    provider_name = config.get("provider", "mock")

    if provider_name not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unknown LLM provider '{provider_name}'. "
            f"Supported: {sorted(SUPPORTED_PROVIDERS)}"
        )

    if provider_name == "mock":
        return MockLLMProvider()

    if provider_name == "openai_compatible":
        base_url = config.get("base_url")
        model = config.get("model")
        if not base_url or not model:
            raise ValueError(
                "openai_compatible provider requires 'base_url' and 'model' in config"
            )
        return OpenAICompatibleProvider(
            base_url=base_url,
            model=model,
            api_key=config.get("api_key"),
            timeout_seconds=config.get("timeout_seconds", 30.0),
        )

    raise AssertionError("unreachable")
