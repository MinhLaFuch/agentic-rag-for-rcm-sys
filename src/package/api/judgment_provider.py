"""
JudgmentProvider abstraction for structured LLM judgments (TypeSafe Jev, etc.).

This is separate from LLMProvider (chat completions) because Jev-style
structured judgments have a fundamentally different API:
- Input: state + typed questions (noul/choice/score)
- Output: structured answers with probabilities/confidence
- Endpoint: /v1/systemone (not /chat/completions)

Business logic for evaluation/judging should depend on JudgmentProvider interface,
not concrete implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class JudgmentProvider(ABC):
    """
    Interface for structured judgment providers (TypeSafe Jev, etc.).

    Every implementation must provide evaluate() method that takes:
    - state: content to evaluate (string, object, or array)
    - questions: map of question_id -> question spec with type field
    Returns: (response_dict, usage_dict) where response has answers per question_id
    """

    provider_name: str = "base"

    @abstractmethod
    def evaluate(
        self,
        state: str | dict[str, Any] | list[Any],
        questions: dict[str, dict[str, Any]],
        enable_long_context: bool = False,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        raise NotImplementedError

    def health_check(self) -> bool:
        return True

    def close(self) -> None:
        pass

    def __enter__(self) -> "JudgmentProvider":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
