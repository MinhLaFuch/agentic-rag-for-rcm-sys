from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMMessage:

    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResponse:
    text: str
    raw: Any = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_seconds: float | None = None
    provider_name: str = ""
    model_name: str = ""
    metadata: dict = field(default_factory=dict)


class LLMProviderError(RuntimeError):
    """Lỗi chung khi gọi LLM provider (timeout, auth, rate limit...)."""


class LLMProvider(ABC):
    provider_name: str = "base"

    @abstractmethod
    def complete(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int = 512,
        response_format_json: bool = False,
    ) -> LLMResponse:
        """
        Gửi messages tới LLM và trả về response chuẩn hoá.

        response_format_json=True nghĩa là caller (ví dụ RerankingTool)
        mong đợi output là JSON hợp lệ (mục XIV: "Output của LLM phải
        structured JSON"). Provider implementation nên cố gắng ép định
        dạng JSON nếu backend hỗ trợ (ví dụ json_mode của OpenAI-compatible
        API); nếu không hỗ trợ, vẫn trả text thô và để caller tự parse +
        validate, KHÔNG tự bịa dữ liệu.
        """
        raise NotImplementedError

    def health_check(self) -> bool:
        """Kiểm tra provider có sẵn sàng không. Override nếu cần."""
        return True
