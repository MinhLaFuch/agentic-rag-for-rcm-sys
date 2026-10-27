"""
Jev (TypeSafe AI) client wrapper for structured judgments.

Jev is a System One model that returns structured decisions (Choice/Score/Noul)
rather than free-form text. It takes a state (string/object/array) and typed questions,
returning answers with probabilities and confidence.

API: https://docs.typesafe.ai/api
"""

from __future__ import annotations

import os
from typing import Any

import httpx

# Default timeout for Jev API calls
DEFAULT_TIMEOUT = 30.0


class JevClient:
    """Client for TypeSafe AI's Jev System One model."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "jev-latest",
        base_url: str = "https://api.typesafe.ai",
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """
        Initialize Jev client.

        Args:
            api_key: TypeSafe API key. If None, reads from TYPESAFE_API_KEY env var.
            model: Model to use (default: jev-latest).
            base_url: API base URL (default: https://api.typesafe.ai).
            timeout: Request timeout in seconds.
        """
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
        """
        Evaluate state against typed questions using Jev.

        Args:
            state: Content to evaluate (string, object, or array).
            questions: Map of question IDs to Question objects with type field.
                       Types: "noul" (yes/no), "choice" (select option), "score" (rubric).
            enable_long_context: Set TypeSafe-Danger-Zone-Long-Context header for long context.

        Returns:
            Tuple of (response, usage) where response has answers under the same keys as
            questions, plus model, and usage has "input_tokens" and "output_tokens".

        Example:
            client = JevClient()
            response, usage = client.evaluate(
                state="I was charged twice. Please help.",
                questions={
                    "billing": {
                        "type": "noul",
                        "instructions": "Is this message about billing?"
                    }
                }
            )
            # response["answers"]["billing"]["noul"] → 0.98
        """
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

        result = response.json()
        usage = result.get("usage", {"input_tokens": 0, "output_tokens": 0})

        return result, usage

    def evaluate_noul(
        self,
        state: str | dict[str, Any] | list[Any],
        instructions: str,
        question_id: str = "default",
        enable_long_context: bool = False,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        """
        Convenience method for a single Noul (yes/no probability) question.

        Args:
            state: Content to evaluate.
            instructions: Question instructions.
            question_id: ID for the question (default: "default").
            enable_long_context: Enable long context header.

        Returns:
            Tuple of (answer, usage) where answer has "noul" field (0-1 probability)
            and "confidence", and usage has "input_tokens" and "output_tokens".
        """
        questions = {
            question_id: {
                "type": "noul",
                "instructions": instructions,
            }
        }
        result = self.evaluate(state, questions, enable_long_context)
        return result["answers"][question_id], result.get("usage", {"input_tokens": 0, "output_tokens": 0})

    def evaluate_choice(
        self,
        state: str | dict[str, Any] | list[Any],
        instructions: str,
        criteria: dict[str, str],
        question_id: str = "default",
        enable_long_context: bool = False,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        """
        Convenience method for a single Choice question.

        Args:
            state: Content to evaluate.
            instructions: Question instructions.
            criteria: Map of option IDs to descriptions.
            question_id: ID for the question (default: "default").
            enable_long_context: Enable long context header.

        Returns:
            Tuple of (answer, usage) where answer has "choice", "probabilities",
            and "confidence", and usage has "input_tokens" and "output_tokens".
        """
        questions = {
            question_id: {
                "type": "choice",
                "instructions": instructions,
                "criteria": criteria,
            }
        }
        result = self.evaluate(state, questions, enable_long_context)
        return result["answers"][question_id], result.get("usage", {"input_tokens": 0, "output_tokens": 0})

    def evaluate_score(
        self,
        state: str | dict[str, Any] | list[Any],
        instructions: str,
        criteria: list[str],
        question_id: str = "default",
        enable_long_context: bool = False,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        """
        Convenience method for a single Score question.

        Args:
            state: Content to evaluate.
            instructions: Question instructions.
            criteria: List of rubric levels (ordered from low to high).
            question_id: ID for the question (default: "default").
            enable_long_context: Enable long context header.

        Returns:
            Tuple of (answer, usage) where answer has "score", "probabilities",
            "confidence", and "legend", and usage has "input_tokens" and "output_tokens".
        """
        questions = {
            question_id: {
                "type": "score",
                "instructions": instructions,
                "criteria": criteria,
            }
        }
        result = self.evaluate(state, questions, enable_long_context)
        return result["answers"][question_id], result.get("usage", {"input_tokens": 0, "output_tokens": 0})

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self) -> "JevClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
