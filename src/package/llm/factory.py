"""
Factory tạo LLMProvider từ config (mục XX, XXI).

Agent/tool code chỉ nên gọi `build_llm_provider(config)`, không tự
`import` provider cụ thể. Điều này giữ đúng nguyên tắc: business logic
không phụ thuộc trực tiếp vào một provider.
"""

from __future__ import annotations

from typing import Any

from .base import LLMProvider
from .providers.openai_compatible import OpenAICompatibleProvider


def build_llm_provider(config: dict[str, Any]) -> LLMProvider:
    """
    config kỳ vọng có dạng (xem configs/agent/llm.yaml):
        provider: openai_compatible
        model: <model name>
        base_url: <URL của OpenAI-compatible server>
        api_key: <để trống nếu server local không cần auth>
    """
    provider = config.get("provider", "openai_compatible")
    if provider == "openai_compatible":
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
    raise ValueError(
        f"Unknown LLM provider: {provider!r}. Supported providers: openai_compatible"
    )

