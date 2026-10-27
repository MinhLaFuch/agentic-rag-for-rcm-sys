"""ScriptedLLM: deterministic LLM for testing (no real API calls)."""

from typing import Any

from package.api import LLMMessage, LLMProvider, LLMProviderError
from package.api._dataclass import LLMResponse


class ScriptedLLM(LLMProvider):
    """
    LLM giả trả về phản hồi viết sẵn cho testing.
    Mỗi phần tử trong script có thể là:
    - chuỗi text (LLMResponse.text)
    - None (mô phỏng resp.text=None)
    - chuỗi rỗng
    - LLMProviderError (để ném)
    Hết script mà vẫn được gọi → AssertionError.
    Ghi lại mọi lần gọi để test kiểm tra nội dung.
    """

    provider_name = "scripted"

    def __init__(
        self,
        *script: str | None | LLMProviderError,
        prompt_tokens: int = 10,
        completion_tokens: int = 5,
        latency_seconds: float = 0.1,
    ) -> None:
        self._script = list(script)
        self._calls: list[dict[str, Any]] = []
        self._prompt_tokens = prompt_tokens
        self._completion_tokens = completion_tokens
        self._latency_seconds = latency_seconds

    @property
    def calls(self) -> list[dict[str, Any]]:
        """List of calls with messages and parameters."""
        return self._calls

    def complete(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int = 512,
        response_format_json: bool = False,
    ) -> LLMResponse:
        if not self._script:
            raise AssertionError(
                f"ScriptedLLM exhausted: {len(self._calls)} call(s) made, but no more responses scripted. "
                f"Add more responses to ScriptedLLM(...) or check test logic."
            )
        response = self._script.pop(0)
        self._calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format_json": response_format_json,
            }
        )
        if isinstance(response, LLMProviderError):
            raise response
        if response is None:
            text = None
        elif isinstance(response, str):
            text = response
        else:
            raise TypeError(f"Script element must be str/None/LLMProviderError, got {type(response)}")
        return LLMResponse(
            text=text,
            prompt_tokens=self._prompt_tokens,
            completion_tokens=self._completion_tokens,
            latency_seconds=self._latency_seconds,
            provider_name="scripted",
            model_name="scripted-0",
        )
