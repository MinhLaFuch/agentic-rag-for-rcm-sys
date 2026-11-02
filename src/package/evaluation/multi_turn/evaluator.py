"""Multi-turn conversation evaluator.

Evaluates conversations at both turn-level and conversation-level.
"""

from __future__ import annotations

import time
from typing import Any
from collections import defaultdict

from ._schema import Conversation, TurnResult, ConversationResult, ConversationSummary
from package.agents.session import Session


class MultiTurnEvaluator:
    """Evaluator for multi-turn conversations."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    def evaluate_conversation(
        self,
        conversation: Conversation,
        agent_runner: Any,
        git_sha: str = "",
    ) -> ConversationResult:
        """Evaluate a full conversation.

        Args:
            conversation: Conversation to evaluate
            agent_runner: Agent runner that can execute turns
            git_sha: Git commit SHA

        Returns:
            ConversationResult with turn results and conversation-level metrics
        """
        turn_results = []
        total_latency = 0.0
        total_tokens = {"prompt_tokens": 0, "completion_tokens": 0}
        conversation_success = True
        failure_stage = None
        error = None

        # Initialize session from initial context
        session = self._initialize_session(conversation.initial_context)

        for turn_input in conversation.turns:
            # Execute the turn
            start_time = time.perf_counter()
            try:
                turn_output = agent_runner.run_turn(turn_input, session)
                success = True
                turn_error = None
            except Exception as e:
                turn_output = None
                success = False
                turn_error = str(e)
                conversation_success = False
                failure_stage = f"turn_{turn_input.position}"
                error = turn_error

            latency = time.perf_counter() - start_time
            total_latency += latency

            # Score the turn
            metrics = self._score_turn(
                turn_input=turn_input,
                turn_output=turn_output,
                session_state=session.to_dict() if hasattr(session, "to_dict") else {},
            )

            # Extract token usage if available
            token_usage = self._extract_token_usage(turn_output)
            if token_usage:
                total_tokens["prompt_tokens"] += token_usage.get("prompt_tokens", 0)
                total_tokens["completion_tokens"] += token_usage.get("completion_tokens", 0)

            # Create turn result
            turn_result = TurnResult(
                turn_id=turn_input.turn_id,
                actual_items=turn_output.get("items", []) if turn_output else [],
                actual_exclusions=turn_output.get("exclusions", {}) if turn_output else {},
                session_state=session.to_dict() if hasattr(session, "to_dict") else {},
                success=success,
                error=turn_error,
                metrics=metrics,
                latency_seconds=latency,
                trace=turn_output or {},
            )
            turn_results.append(turn_result)

            # Update session for next turn
            if success and turn_output:
                self._update_session(session, turn_output)

            # Stop if conversation failed
            if not success:
                break

        # Calculate conversation-level metrics
        conversation_metrics = self._calculate_conversation_metrics(
            turn_results=turn_results,
            conversation=conversation,
        )

        return ConversationResult(
            conversation_id=conversation.conversation_id,
            turn_results=turn_results,
            conversation_success=conversation_success,
            failure_stage=failure_stage,
            error=error,
            metrics=conversation_metrics,
            latency_seconds=total_latency,
            token_usage=total_tokens if total_tokens["prompt_tokens"] > 0 else None,
            git_sha=git_sha,
            provenance={
                "conversation_metadata": conversation.metadata,
                "turn_count": len(conversation.turns),
            },
        )

    def _initialize_session(self, initial_context: dict[str, Any]) -> Session:
        """Initialize session from initial context.

        Creates a real Session object and applies initial context.
        """
        session = Session()
        if initial_context:
            session.update_constraints(initial_context)
        return session

    def _score_turn(
        self,
        turn_input: Any,
        turn_output: dict[str, Any] | None,
        session_state: dict[str, Any],
    ) -> dict[str, float]:
        """Score a single turn.

        Args:
            turn_input: TurnInput
            turn_output: Actual output from agent
            session_state: Session state after the turn

        Returns:
            Dict of metric names to values
        """
        metrics = {
            "turn_success": 1.0 if turn_output is not None else 0.0,
            "item_match_rate": 0.0,
            "exclusion_compliance": 0.0,
            "reference_correctness": 0.0,
        }

        if turn_output is None:
            return metrics

        # Check if expected items match actual items
        expected_items = set(turn_input.expected_items)
        actual_items = set(turn_output.get("items", []))
        if expected_items:
            metrics["item_match_rate"] = len(expected_items & actual_items) / len(expected_items)
        else:
            metrics["item_match_rate"] = 1.0  # No expectation

        # Check exclusion compliance
        expected_exclusions = turn_input.expected_exclusions
        actual_exclusions = turn_output.get("exclusions", {})
        if expected_exclusions:
            compliance = True
            for key, expected in expected_exclusions.items():
                actual = actual_exclusions.get(key)
                # Handle both list values (item_ids, categories) and scalar values (price_max, etc.)
                if isinstance(expected, list):
                    if not set(expected).issubset(set(actual or [])):
                        compliance = False
                else:
                    # Scalar comparison
                    if actual != expected:
                        compliance = False
            metrics["exclusion_compliance"] = 1.0 if compliance else 0.0
        else:
            metrics["exclusion_compliance"] = 1.0

        # Check reference correctness (if turn uses references to previous turns)
        if "$" in str(turn_output):
            metrics["reference_correctness"] = 1.0  # Placeholder: assume correct if references used
        else:
            metrics["reference_correctness"] = 1.0

        return metrics

    def _extract_token_usage(self, turn_output: dict[str, Any] | None) -> dict[str, int] | None:
        """Extract token usage from turn output."""
        if turn_output and "usage" in turn_output:
            return turn_output["usage"]
        return None

    def _update_session(self, session: Any, turn_output: dict[str, Any]) -> None:
        """Update session state based on turn output."""
        # Update shown items
        items = turn_output.get("items", [])
        if hasattr(session, "add_shown_items"):
            session.add_shown_items(items)
        else:
            session["shown_items"].extend(items)

        # Update constraints
        exclusions = turn_output.get("exclusions", {})
        if exclusions and hasattr(session, "add_exclusions"):
            session.add_exclusions(
                item_ids=exclusions.get("exclude_item_ids"),
                categories=exclusions.get("exclude_categories"),
            )
        elif exclusions:
            session["constraints"].update(exclusions)

    def _calculate_conversation_metrics(
        self,
        turn_results: list[TurnResult],
        conversation: Conversation,
    ) -> dict[str, float]:
        """Calculate conversation-level metrics.

        Args:
            turn_results: List of turn results
            conversation: Original conversation

        Returns:
            Dict of metric names to values
        """
        metrics = {}

        # Turn success rate
        if turn_results:
            metrics["turn_success_rate"] = sum(1 for tr in turn_results if tr.success) / len(turn_results)
        else:
            metrics["turn_success_rate"] = 0.0

        # Conversation success
        metrics["conversation_success"] = 1.0 if all(tr.success for tr in turn_results) else 0.0

        # Average item match rate
        item_match_rates = [tr.metrics.get("item_match_rate", 0.0) for tr in turn_results]
        if item_match_rates:
            metrics["avg_item_match_rate"] = sum(item_match_rates) / len(item_match_rates)
        else:
            metrics["avg_item_match_rate"] = 0.0

        # Exclusion compliance across all turns
        exclusion_compliance = [tr.metrics.get("exclusion_compliance", 0.0) for tr in turn_results]
        if exclusion_compliance:
            metrics["exclusion_compliance"] = sum(exclusion_compliance) / len(exclusion_compliance)
        else:
            metrics["exclusion_compliance"] = 1.0

        # Context retention: check if session state grows appropriately
        if turn_results:
            # Check if session.shown_items grows with each turn (for "more items" scenarios)
            shown_items_counts = [
                len(tr.session_state.get("shown_items", [])) for tr in turn_results
            ]
            if len(shown_items_counts) > 1:
                # Check monotonic growth (non-decreasing for "more items")
                monotonic = all(shown_items_counts[i] <= shown_items_counts[i+1] for i in range(len(shown_items_counts)-1))
                metrics["context_retention"] = 1.0 if monotonic else 0.0
            else:
                metrics["context_retention"] = 1.0
        else:
            metrics["context_retention"] = 1.0

        # Reference resolution accuracy
        reference_correctness = [tr.metrics.get("reference_correctness", 0.0) for tr in turn_results]
        if reference_correctness:
            metrics["reference_accuracy"] = sum(reference_correctness) / len(reference_correctness)
        else:
            metrics["reference_accuracy"] = 1.0

        return metrics

    def evaluate_conversations(
        self,
        conversations: list[Conversation],
        agent_runner: Any,
        git_sha: str = "",
    ) -> ConversationSummary:
        """Evaluate multiple conversations.

        Args:
            conversations: List of conversations to evaluate
            agent_runner: Agent runner
            git_sha: Git commit SHA

        Returns:
            ConversationSummary with aggregated metrics
        """
        results = []
        all_turn_results = []

        for conv in conversations:
            result = self.evaluate_conversation(conv, agent_runner, git_sha)
            results.append(result)
            all_turn_results.extend(result.turn_results)

        # Calculate summary metrics
        total_conversations = len(results)
        turn_success_rate = (
            sum(1 for r in results for tr in r.turn_results if tr.success) / sum(len(r.turn_results) for r in results)
            if results and sum(len(r.turn_results) for r in results) > 0
            else 0.0
        )
        conversation_success_rate = sum(1 for r in results if r.conversation_success) / total_conversations if total_conversations > 0 else 0.0

        # Aggregate conversation-level metrics
        metrics = self._aggregate_metrics(results)

        # Aggregate latency
        latencies = [r.latency_seconds for r in results]
        latency = {
            "mean": sum(latencies) / len(latencies) if latencies else 0.0,
            "min": min(latencies) if latencies else 0.0,
            "max": max(latencies) if latencies else 0.0,
        }

        # Failure distribution
        failure_distribution = defaultdict(int)
        for r in results:
            if r.failure_stage:
                failure_distribution[r.failure_stage] += 1

        # Context retention metrics
        context_retention = [
            r.metrics.get("context_retention", 0.0) for r in results
        ]
        context_retention_metrics = {
            "mean": sum(context_retention) / len(context_retention) if context_retention else 0.0,
        }

        return ConversationSummary(
            total_conversations=total_conversations,
            turn_success_rate=turn_success_rate,
            conversation_success_rate=conversation_success_rate,
            metrics=metrics,
            latency=latency,
            failure_distribution=dict(failure_distribution),
            context_retention_metrics=context_retention_metrics,
            git_sha=git_sha,
        )

    def _aggregate_metrics(self, results: list[ConversationResult]) -> dict[str, float]:
        """Aggregate metrics across conversations."""
        metric_keys = set()
        for r in results:
            metric_keys.update(r.metrics.keys())

        aggregated = {}
        for key in sorted(metric_keys):
            values = [r.metrics[key] for r in results if key in r.metrics]
            if values:
                aggregated[f"{key}_mean"] = sum(values) / len(values)
                aggregated[f"{key}_std"] = (sum((v - aggregated[f"{key}_mean"])**2 for v in values) / len(values))**0.5 if len(values) > 1 else 0.0
                aggregated[f"{key}_min"] = min(values)
                aggregated[f"{key}_max"] = max(values)

        return aggregated
