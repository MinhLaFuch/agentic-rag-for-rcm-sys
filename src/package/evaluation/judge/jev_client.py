"""
Jev (TypeSafe AI) client wrapper for structured judgments.

Jev is a System One model that returns structured decisions (Choice/Score/Noul)
rather than free-form text. It takes a state (string/object/array) and typed questions,
returning answers with probabilities and confidence.

API: https://docs.typesafe.ai/api

NOTE: This module is deprecated. Use package.api.JevProvider instead.
This module is kept for backward compatibility and will be removed in a future version.
"""

from __future__ import annotations

import warnings
from typing import Any

from package.api import JevProvider


class JevClient(JevProvider):
    """Client for TypeSafe AI's Jev System One model.

    Deprecated: Use package.api.JevProvider directly.
    """

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
        warnings.warn(
            "package.evaluation.judge.JevClient is deprecated. "
            "Use package.api.JevProvider instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout=timeout,
        )

    # The evaluate, evaluate_noul, evaluate_choice, evaluate_score, close,
    # __enter__, __exit__ methods are inherited from JevProvider