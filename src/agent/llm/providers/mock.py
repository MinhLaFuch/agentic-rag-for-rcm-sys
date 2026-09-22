"""
MockLLMProvider — provider deterministic, không gọi network, không cần API key.

Mục đích:
  - Cho phép unit test agent/tool logic (mục XXIV) mà không phụ thuộc
    LLM thật (không tốn cost, không flaky do model non-determinism).
  - Dùng làm default provider trong Phase 1-7 (trước khi Agent layer
    thật sự cần LLM ở Phase 8), để pipeline có thể chạy end-to-end
    smoke test sớm mà không cần credential.

KHÔNG dùng MockLLMProvider để báo cáo "kết quả agent" thật (mục XXVIII —
không tạo dữ liệu giả để thay experiment thực). Provider này chỉ dùng
cho testing/development.
"""

from __future__ import annotations

import json
import time

from ..base import LLMMessage, LLMProvider, LLMResponse


class MockLLMProvider(LLMProvider):
    provider_name = "mock"

    def __init__(self, canned_response: str | None = None) -> None:
        self._canned_response = canned_response

    def complete(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int = 512,
        response_format_json: bool = False,
    ) -> LLMResponse:
        start = time.monotonic()

        if self._canned_response is not None:
            text = self._canned_response
        elif response_format_json:
            # Trả về JSON hợp lệ tối thiểu, đúng format mục XIV yêu cầu
            # cho RerankingTool: {"item_id": ..., "score": ..., "reasons": [...]}.
            text = json.dumps(
                {
                    "item_id": "MOCK_ITEM",
                    "score": 0.0,
                    "reasons": ["mock provider — no real reasoning performed"],
                }
            )
        else:
            last_user = next(
                (m.content for m in reversed(messages) if m.role == "user"), ""
            )
            text = f"[MOCK RESPONSE] echo: {last_user[:200]}"

        latency = time.monotonic() - start
        return LLMResponse(
            text=text,
            raw={"messages": [m.__dict__ for m in messages]},
            prompt_tokens=sum(len(m.content.split()) for m in messages),
            completion_tokens=len(text.split()),
            latency_seconds=latency,
            provider_name=self.provider_name,
            model_name="mock-0",
        )

    def health_check(self) -> bool:
        return True
