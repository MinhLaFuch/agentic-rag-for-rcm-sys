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


def get_mock_llm() -> MockLLMProvider:
    """Return mock LLM with basic responses."""
    return MockLLMProvider(
        {
            "video games under $50": {
                "text": '{"steps": [{"tool": "SQLTool", "args": {"filters": {"price_max": 50, "domain": "Video_Games"}, "limit": 10}}]}'
            },
            "action games similar": {
                "text": '{"steps": [{"tool": "ItemCFTool", "args": {"items": ["item_vg_123"], "top_k": 10}}, {"tool": "SQLTool", "args": {"filters": {"price_max": 100}, "candidates": "$1.candidates", "limit": 10}}]}'
            },
            "what kind of games": {
                "text": '{"ask_user": "Could you specify what type of games you are looking for (e.g., action, puzzle, strategy)?"}'
            },
            "user_unknown": {
                "text": '{"ask_user": "I do not have information about this user. Could you provide your user ID?"}'
            },
        }
    )
