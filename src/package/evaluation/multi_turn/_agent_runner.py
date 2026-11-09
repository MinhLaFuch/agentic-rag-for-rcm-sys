"""Real agent runner for multi-turn evaluation (Phase 4.4).

Wraps the production PlanExecutor + Session + real LLM provider over the
fixture corpus — the same tool stack as the planner benchmark. Requires
LLM_BASE_URL/LLM_API_KEY (configs/agent/llm.yaml); without them construction
fails loudly instead of silently degrading.
"""

from __future__ import annotations

from typing import Any

from package.agents import PlanExecutor, build_tools
from package.agents.results import extract_recommendations
from package.api import build_llm_provider
from package.config import load_config
from package.recommenders import ItemKNNRecommender
from package.tools import BaselineScorer

from ..component.benchmarks.fixtures.create_test_corpus import create_test_corpus
from ..component.benchmarks.fixtures.create_test_interactions import create_test_interactions
from ..component.benchmarks.fixtures.create_test_mappings import create_test_mappings

# Filter keys that act as exclusions/constraints for scoring
_EXCLUSION_FILTER_KEYS = ("exclude_item_ids", "exclude_categories", "price_max", "price_min", "categories_any", "categories_all", "store", "domain")


class RealAgentRunner:
    """run_turn(turn_input, session) -> dict for MultiTurnEvaluator."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        llm_cfg = self.config.get("llm") or load_config("agent/llm")
        if not llm_cfg.get("base_url"):
            raise ValueError(
                "Multi-turn evaluation needs a real LLM: set LLM_BASE_URL "
                "(and LLM_API_KEY) or pass config {'llm': {...}}."
            )
        self.llm = build_llm_provider(llm_cfg)

        interactions = create_test_interactions()
        user2id, item2id, _ = create_test_mappings(interactions)
        corpus = create_test_corpus()
        knn = ItemKNNRecommender(10).fit(interactions[["user_idx", "item_idx"]])
        agent_tools = build_tools(knn, BaselineScorer(knn), user2id, item2id, interactions, corpus)
        # reflect_rounds from agent.yaml default; session is bound per turn
        self.executor = PlanExecutor(llm=self.llm, tools=agent_tools.for_planner_memory())

    def run_turn(self, turn_input: Any, session: Any) -> dict[str, Any]:
        """Execute one turn through the real planner/executor with session state."""
        self.executor.session = session
        results = self.executor.run(turn_input.user_request)

        item_ids = extract_recommendations(results, 50)

        # Surface exclusion/constraint filters actually used by executed steps
        exclusions: dict[str, Any] = {}
        for r in results:
            if not r.get("ok"):
                continue
            filters = (r.get("args") or {}).get("filters") or {}
            for key in _EXCLUSION_FILTER_KEYS:
                if key in filters:
                    exclusions[key] = filters[key]

        return {
            "items": item_ids,
            "exclusions": exclusions,
            "usage": dict(getattr(self.executor, "last_usage", {}) or {}),
            "trace": {
                "steps": results,
                "plan": self.executor.last_plan,
                "question": self.executor.last_question,
                "reflections": self.executor.last_reflections,
            },
        }
