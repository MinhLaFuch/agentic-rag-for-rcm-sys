"""Mock LLM for Planner evaluation.

Returns deterministic responses based on request for testing.
"""

from typing import Any

from package.api import LLMMessage, LLMProvider
from package.api._dataclass import LLMResponse


class MockLLMProvider(LLMProvider):
    """Mock LLM that returns canned responses for testing."""

    def __init__(self, responses: dict[str, dict[str, Any]] | None = None) -> None:
        self.responses = responses or {}
        self.last_messages: list[LLMMessage] = []

    def complete(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format_json: bool = False,
    ) -> LLMResponse:
        self.last_messages = messages
        user_msg = messages[-1].content if messages else ""

        # Return canned response if available
        for pattern, response in self.responses.items():
            if pattern in user_msg:
                return LLMResponse(
                    text=response.get("text", '{"steps": []}'),
                    prompt_tokens=100,
                    completion_tokens=50,
                    latency_seconds=0.1,
                )

        # Default fallback: return empty plan
        return LLMResponse(
            text='{"steps": []}',
            prompt_tokens=100,
            completion_tokens=10,
            latency_seconds=0.05,
        )