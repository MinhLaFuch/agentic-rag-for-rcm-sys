"""Fake LLM for testing and mock mode.

ScriptedLLM returns pre-defined responses based on request patterns.
Absorbs MockLLMProvider functionality.
"""

from typing import Any

from package.api import LLMMessage, LLMResponse, LLMProvider


class ScriptedLLM(LLMProvider):
    """Fake LLM that returns scripted responses for testing."""

    provider_name = "scripted"

    def __init__(self, default_script: str = '{"steps": []}'):
        self.default_script = default_script
        self.scripts: dict[str, str] = {}
        self.last_messages: list[LLMMessage] = []

    def add_script(self, pattern: str, response: str):
        """Add a scripted response for requests matching pattern."""
        self.scripts[pattern] = response

    def complete(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format_json: bool = False,
    ) -> LLMResponse:
        self.last_messages = messages
        user_msg = messages[-1].content if messages else ""

        # Return scripted response if available
        for pattern, response in self.scripts.items():
            if pattern in user_msg:
                return LLMResponse(
                    text=response,
                    prompt_tokens=100,
                    completion_tokens=50,
                    latency_seconds=0.1,
                )

        # Default fallback
        return LLMResponse(
            text=self.default_script,
            prompt_tokens=100,
            completion_tokens=10,
            latency_seconds=0.05,
        )

    def health_check(self) -> bool:
        return True
