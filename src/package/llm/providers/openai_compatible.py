"""
OpenAICompatibleProvider — implementation cho bất kỳ server tương thích
OpenAI Chat Completions API (OpenAI thật, vLLM `--api openai`, Ollama
`/v1/chat/completions`, LM Studio...).

Trạng thái Phase 1: implementation hoàn chỉnh; smoke test dùng monkeypatch
urlopen để chạy offline — không cần API key hay server thật trong CI.

BLOCKED:
REASON: chưa có endpoint LLM thật (API key hoặc local server) trong môi
  trường phát triển hiện tại.
REQUIRED ACTION: trước Phase 8, cấu hình `configs/agent/llm.yaml` với
  base_url + api_key (hoặc để trống nếu server local không cần auth) và
  chạy `scripts/check_llm_provider.py` để xác nhận provider hoạt động
  thật trước khi dùng cho Agent layer.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from ..base import LLMProvider
from .._dataclass import LLMMessage, LLMResponse
from .._error import LLMProviderError

class OpenAICompatibleProvider(LLMProvider):
    provider_name = "openai_compatible"

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def complete(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int = 512,
        response_format_json: bool = False,
    ) -> LLMResponse:
        payload: dict = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        request = urllib.request.Request(
            url=f"{self._base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        start = time.monotonic()
        try:
            with urllib.request.urlopen(
                request, timeout=self._timeout_seconds
            ) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:  # HTTPError là con của URLError; TimeoutError nổ lúc resp.read(); JSONDecodeError khi body không phải JSON
            raise LLMProviderError(f"LLM request failed: {exc}") from exc
        latency = time.monotonic() - start

        try:
            text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMProviderError(f"Unexpected response shape: {body}") from exc

        usage = body.get("usage", {})
        return LLMResponse(
            text=text,
            raw=body,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            latency_seconds=latency,
            provider_name=self.provider_name,
            model_name=self._model,
        )

    def health_check(self) -> bool:
        try:
            self.complete(
                [LLMMessage(role="user", content="ping")], max_tokens=1
            )
            return True
        except LLMProviderError:
            return False