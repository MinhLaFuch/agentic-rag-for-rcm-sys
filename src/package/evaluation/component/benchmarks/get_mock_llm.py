"""Factory function for mock LLM."""

from .mock_llm_provider import MockLLMProvider


def get_mock_llm() -> MockLLMProvider:
    """Return mock LLM with basic responses."""
    return MockLLMProvider(
        {
            "video games under $50": {
                "text": '{"steps": [{"tool": "FilterTool", "args": {"filters": {"price_max": 50, "domain": "Video_Games"}, "limit": 10}}]}'
            },
            "action games similar": {
                "text": '{"steps": [{"tool": "SimilarTool", "args": {"items": ["item_vg_123"], "top_k": 10}}, {"tool": "FilterTool", "args": {"filters": {"price_max": 100}, "candidates": "$1.candidates", "limit": 10}}]}'
            },
            "what kind of games": {
                "text": '{"ask_user": "Could you specify what type of games you are looking for (e.g., action, puzzle, strategy)?"}'
            },
            "user_unknown": {
                "text": '{"ask_user": "I do not have information about this user. Could you provide your user ID?"}'
            },
        }
    )