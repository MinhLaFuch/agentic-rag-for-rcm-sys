"""
LLMProvider abstraction (spec mục XXI).

Business logic (agent, tools, reranking, explanation) chỉ được phép phụ thuộc
vào interface `LLMProvider` này, KHÔNG được import trực tiếp SDK của một
provider cụ thể (openai, anthropic, ollama...). Điều này cho phép thay đổi
backend (local LLM / OpenAI-compatible API / Ollama / vLLM / Cloud API) mà
không phải sửa agent/tool logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ._dataclass import LLMMessage, LLMResponse

class LLMProvider(ABC):
    """
    Interface bắt buộc cho mọi LLM backend.

    Mọi implementation (openai-compatible, ollama, vllm...) phải
    kế thừa class này và implement đầy đủ các method abstract.
    """

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
