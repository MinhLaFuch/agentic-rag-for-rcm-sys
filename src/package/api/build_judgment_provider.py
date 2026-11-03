"""
Factory tạo JudgmentProvider từ config (mục XX, XXI).

Business logic cho evaluation/judging chỉ nên gọi `build_judgment_provider(config)`,
không tự `import` provider cụ thể.
"""

from __future__ import annotations

from typing import Any

from .judgment_provider import JudgmentProvider
from .jev_provider import JevProvider


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
