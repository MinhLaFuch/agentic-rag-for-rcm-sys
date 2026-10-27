"""MemoryTool component benchmark implementation."""

from __future__ import annotations

from typing import Any
import pandas as pd

from package.memory.memory_tool import MemoryTool
from package.tools.corpus import ItemCorpus
from .._evaluator import ComponentEvaluator
from .._schema import BenchmarkCase


class MemoryEvaluator(ComponentEvaluator):
    """Evaluator for MemoryTool component."""

    def __init__(
        self,
        interactions: pd.DataFrame,
        user2id: dict[str, int],
        item2id: dict[str, int],
        corpus: ItemCorpus,
        config: dict[str, Any] | None = None,
    ):
        """Initialize the MemoryEvaluator.

        Args:
            interactions: User interaction history
            user2id: Mapping from user_id to user_idx
            item2id: Mapping from item_id to item_idx
            corpus: ItemCorpus with item metadata
            config: Additional configuration
        """
        super().__init__(config)
        self.memory_tool = MemoryTool(interactions, user2id, item2id, corpus)

    def run_component(self, case_input: dict[str, Any]) -> dict[str, Any]:
        """Run MemoryTool with the given input.

        Args:
            case_input: Should contain 'user_id' and optionally 'top_n_categories'

        Returns:
            MemoryTool output
        """
        user_id = case_input["user_id"]
        top_n_categories = case_input.get("top_n_categories", 5)
        return self.memory_tool.execute(user_id, top_n_categories=top_n_categories)

    def score_component(self, actual_output: dict[str, Any], expected: dict[str, Any]) -> dict[str, float]:
        """Score MemoryTool output against expected.

        Metrics:
        - known_correct: Whether 'known' matches expected
        - n_interactions_correct: Whether n_interactions matches expected
        - top_categories_match: Fraction of expected top categories present in actual
        - price_range_correct: Whether price_range matches expected
        - recent_items_match: Fraction of expected recent items present in actual
        """
        metrics = {}

        # known flag
        metrics["known_correct"] = 1.0 if actual_output.get("known") == expected.get("known") else 0.0

        # n_interactions
        metrics["n_interactions_correct"] = (
            1.0 if actual_output.get("n_interactions") == expected.get("n_interactions") else 0.0
        )

        # top_categories
        expected_cats = set(expected.get("top_categories", []))
        actual_cats = set(actual_output.get("top_categories", []))
        if expected_cats:
            metrics["top_categories_match"] = len(expected_cats & actual_cats) / len(expected_cats)
        else:
            metrics["top_categories_match"] = 1.0 if not actual_cats else 0.0

        # price_range
        expected_price = expected.get("price_range")
        actual_price = actual_output.get("price_range")
        if expected_price is None:
            metrics["price_range_correct"] = 1.0 if actual_price is None else 0.0
        elif actual_price is None:
            metrics["price_range_correct"] = 0.0
        else:
            metrics["price_range_correct"] = (
                1.0
                if (
                    actual_price.get("min") == expected_price.get("min")
                    and actual_price.get("max") == expected_price.get("max")
                )
                else 0.0
            )

        # recent_items
        expected_items = set(expected.get("recent_items", []))
        actual_items = set(actual_output.get("recent_items", []))
        if expected_items:
            metrics["recent_items_match"] = len(expected_items & actual_items) / len(expected_items)
        else:
            metrics["recent_items_match"] = 1.0 if not actual_items else 0.0

        return metrics
