"""Fake judge for testing and mock mode.

ScriptedJudge returns pre-defined judgment responses for testing.
"""

from typing import Any

from package.api import LLMProvider, LLMResponse


class ScriptedJudge(LLMProvider):
    """Fake judge that returns scripted responses for testing."""

    provider_name = "scripted_judge"

    def __init__(self, default_response: str = '{"supported": true}'):
        self.default_response = default_response
        self.responses: dict[str, str] = {}

    def add_response(self, pattern: str, response: str):
        """Add a scripted response for requests matching pattern."""
        self.responses[pattern] = response

    def complete(
        self,
        messages: list[Any],
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format_json: bool = False,
    ) -> LLMResponse:
        # Messages format for judge is different, simplify
        if messages and isinstance(messages, list):
            last_content = str(messages[-1]) if messages else ""
        else:
            last_content = str(messages) if messages else ""

        for pattern, response in self.responses.items():
            if pattern in last_content:
                return LLMResponse(
                    text=response,
                    prompt_tokens=100,
                    completion_tokens=50,
                    latency_seconds=0.1,
                )

        return LLMResponse(
            text=self.default_response,
            prompt_tokens=100,
            completion_tokens=10,
            latency_seconds=0.05,
        )

    def health_check(self) -> bool:
        return True
