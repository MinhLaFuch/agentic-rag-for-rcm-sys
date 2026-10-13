from dataclasses import dataclass, field
from typing import Any

@dataclass
class LLMMessage:
    """Một message trong hội thoại gửi tới LLM."""

    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResponse:
    """Kết quả trả về từ LLMProvider — chuẩn hoá giữa các backend khác nhau."""

    text: str
    raw: Any = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_seconds: float | None = None
    provider_name: str = ""
    model_name: str = ""
    metadata: dict = field(default_factory=dict)