"""MemoryTool correctness evaluator (scored against the independent oracle)."""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from package.data.leakage import LeakageError
from package.memory.memory_tool import MemoryTool
from package.tools.corpus import ItemCorpus
from .._evaluator import ComponentEvaluator
from .memory_correctness_setup import get_interactions_without_rating


class MemoryCorrectnessEvaluator(ComponentEvaluator):
    """Runs MemoryTool and compares every profile field with the oracle.

    Case input:
      user_id, top_n_categories (default 5), as_of_timestamp (optional),
      snapshot_mode: "pretruncated" (default; interactions are cut to ts <= as_of before the
        tool sees them, which is how a point-in-time snapshot is meant to be built) or
        "untruncated" (full frame is passed with an as_of; the tool's leakage guard must raise).
    Case expected:
      a profile dict, or {"expect_error": "LeakageError"}; optional "leakage_probe"
      (see memory_oracle.leakage_probe).
    """

    def __init__(
        self,
        interactions: pd.DataFrame,
        user2id: dict[str, int],
        item2id: dict[str, int],
        meta: pd.DataFrame,
        config: dict[str, Any] | None = None,
        tool_factory: Callable[..., Any] = MemoryTool,  # injectable so tests can plant a leaky tool
    ):
        super().__init__(config)
        self.interactions = interactions
        self.user2id = user2id
        self.item2id = item2id
        self.meta = meta
        self.corpus = ItemCorpus.from_dataframe(meta)
        self.tool_factory = tool_factory

    def run_component(self, case_input: dict[str, Any]) -> dict[str, Any]:
        user_id = case_input["user_id"]
        top_n = case_input.get("top_n_categories", 5)
        as_of = case_input.get("as_of_timestamp")
        mode = case_input.get("snapshot_mode", "pretruncated")

        df = self.interactions
        if as_of is not None and mode == "pretruncated":
            df = df[df["timestamp"] <= as_of]
        # For u_no_rating case, drop the rating column
        if user_id == "u_no_rating":
            df = get_interactions_without_rating(df, user_id)
        try:
            tool = self.tool_factory(df, self.user2id, self.item2id, self.corpus, as_of_timestamp=as_of)
            return tool.execute(user_id, top_n_categories=top_n)
        except LeakageError as e:
            return {"error_type": "LeakageError", "message": str(e)}

    def score_component(self, actual_output: dict[str, Any], expected: dict[str, Any]) -> dict[str, float]:
        raised = actual_output.get("error_type")
        if "expect_error" in expected:
            ok = 1.0 if raised == expected["expect_error"] else 0.0
            return {"error_behavior_correct": ok, "all_fields_match": ok}
        if raised:  # unexpected error
            return {k: 0.0 for k in (
                "known_correct", "n_interactions_correct", "top_categories_exact", "price_range_exact",
                "recent_items_exact", "all_fields_match")}

        m: dict[str, float] = {}
        m["known_correct"] = float(actual_output.get("known") == expected["known"])
        m["n_interactions_correct"] = float(actual_output.get("n_interactions") == expected["n_interactions"])
        m["top_categories_exact"] = float(actual_output.get("top_categories") == expected["top_categories"])
        m["top_categories_set_match"] = float(
            set(actual_output.get("top_categories", [])) == set(expected["top_categories"]))
        m["price_range_exact"] = float(actual_output.get("price_range") == expected["price_range"])
        m["recent_items_exact"] = float(actual_output.get("recent_items") == expected["recent_items"])
        m["recent_items_set_match"] = float(
            set(actual_output.get("recent_items", [])) == set(expected["recent_items"]))

        # Love/hate fields
        m["love_categories_exact"] = float(actual_output.get("love_categories") == expected["love_categories"])
        m["love_categories_set_match"] = float(
            set(actual_output.get("love_categories", [])) == set(expected["love_categories"]))
        m["hate_categories_exact"] = float(actual_output.get("hate_categories") == expected["hate_categories"])
        m["hate_categories_set_match"] = float(
            set(actual_output.get("hate_categories", [])) == set(expected["hate_categories"]))
        m["loved_items_exact"] = float(actual_output.get("loved_items") == expected["loved_items"])
        m["loved_items_set_match"] = float(
            set(actual_output.get("loved_items", [])) == set(expected["loved_items"]))
        m["hated_items_exact"] = float(actual_output.get("hated_items") == expected["hated_items"])
        m["hated_items_set_match"] = float(
            set(actual_output.get("hated_items", [])) == set(expected["hated_items"]))

        m["all_fields_match"] = float(all(m[k] == 1.0 for k in (
            "known_correct", "n_interactions_correct", "top_categories_exact",
            "price_range_exact", "recent_items_exact", "love_categories_exact",
            "hate_categories_exact", "loved_items_set_match", "hated_items_set_match")))

        probe = expected.get("leakage_probe")
        if probe is not None:
            future = set(probe["future_only_items"])
            leaked = (actual_output.get("n_interactions", 0) > probe["max_n_interactions"]
                      or bool(future & set(actual_output.get("recent_items", []))))
            m["future_leakage"] = float(leaked)  # lower is better; must be 0.0
        return m
