"""
Factory tạo LLMProvider từ config (mục XX, XXI).

Agent/tool code chỉ nên gọi `build_llm_provider(config)`, không tự
`import` provider cụ thể. Điều này giữ đúng nguyên tắc: business logic
không phụ thuộc trực tiếp vào một provider.
"""

from __future__ import annotations

from typing import Any

from .llm_provider import LLMProvider
from .openai_compatible_provider import OpenAICompatibleProvider
from .judgment_provider import JudgmentProvider, JevProvider


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
            timeout_seconds=float(config["timeout_seconds"]),
        )
    raise ValueError(
        f"Unknown LLM provider: {provider!r}. Supported providers: openai_compatible"
    )


def build_judgment_provider(config: dict[str, Any]) -> JudgmentProvider:
    """
    Factory tạo JudgmentProvider từ config.

    config kỳ vọng có dạng (xem configs/eval/judge.yaml):
        provider: jev
        model: <model name> (default: jev-latest)
        base_url: <API base URL> (default: https://api.typesafe.ai)
        api_key: <API key hoặc đọc từ env TYPESAFE_API_KEY>
        timeout_seconds: <timeout> (default: 30.0)
    """
    provider = config.get("provider", "jev")
    if provider == "jev":
        return JevProvider(
            api_key=config.get("api_key"),
            model=config.get("model", "jev-latest"),
            base_url=config.get("base_url", "https://api.typesafe.ai"),
            timeout=float(config.get("timeout_seconds", 30.0)),
        )
    raise ValueError(
        f"Unknown judgment provider: {provider!r}. Supported providers: jev"
    )

