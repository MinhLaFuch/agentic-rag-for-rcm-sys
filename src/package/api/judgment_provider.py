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
class JevProvider(JudgmentProvider):
    """TypeSafe AI Jev System One provider for structured judgments."""

    provider_name = "jev"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "jev-latest",
        base_url: str = "https://api.typesafe.ai",
        timeout: float = 30.0,
    ) -> None:
        import os
        import httpx

        self.api_key = api_key or os.environ.get("TYPESAFE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "TYPESAFE_API_KEY not set. Set it via api_key parameter or "
                "TYPESAFE_API_KEY environment variable."
            )

        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)

    def evaluate(
        self,
        state: str | dict[str, Any] | list[Any],
        questions: dict[str, dict[str, Any]],
        enable_long_context: bool = False,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        if enable_long_context:
            headers["TypeSafe-Danger-Zone-Long-Context"] = "true"

        payload = {
            "model": self.model,
            "state": state,
            "questions": questions,
        }

        response = self.client.post(
            f"{self.base_url}/v1/systemone",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()

        data = response.json()
        usage = data.get("usage", {"input_tokens": 0, "output_tokens": 0})
        return data, usage

    def close(self) -> None:
        self.client.close()

    def evaluate_noul(
        self,
        state: str | dict[str, Any] | list[Any],
        instructions: str,
        question_id: str = "default",
        enable_long_context: bool = False,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        questions = {
            question_id: {
                "type": "noul",
                "instructions": instructions,
            }
        }
        return self.evaluate(state, questions, enable_long_context)

    def evaluate_choice(
        self,
        state: str | dict[str, Any] | list[Any],
        instructions: str,
        criteria: dict[str, str],
        question_id: str = "default",
        enable_long_context: bool = False,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        questions = {
            question_id: {
                "type": "choice",
                "instructions": instructions,
                "criteria": criteria,
            }
        }
        return self.evaluate(state, questions, enable_long_context)

    def evaluate_score(
        self,
        state: str | dict[str, Any] | list[Any],
        instructions: str,
        criteria: list[str],
        question_id: str = "default",
        enable_long_context: bool = False,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        questions = {
            question_id: {
                "type": "score",
                "instructions": instructions,
                "criteria": criteria,
            }
        }
        return self.evaluate(state, questions, enable_long_context)