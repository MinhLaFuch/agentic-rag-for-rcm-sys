"""Schema definitions for multi-turn conversation evaluation.

Distinguishes turn-level evaluation from conversation-level evaluation.
A conversation may fail even if most individual turns succeed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone
import hashlib
import json


MULTI_TURN_VERSION = "1.0.0"


@dataclass
class TurnInput:
    """Input for a single conversation turn.

    Attributes:
        turn_id: Unique identifier for this turn
        position: Position in the conversation (0-indexed)
        user_request: The user's request text
        expected_state: Expected session state before this turn (for validation)
        expected_behavior: Expected behavior description
        expected_items: Expected items to be recommended (if applicable)
        expected_exclusions: Expected items/categories to exclude (if applicable)
    """
    turn_id: str
    position: int
    user_request: str
    expected_state: dict[str, Any] = field(default_factory=dict)
    expected_behavior: str = ""
    expected_items: list[str] = field(default_factory=list)
    expected_exclusions: dict[str, list[str]] = field(default_factory=dict)
    # Filter/constraint keys that must NOT appear in the turn's actual
    # exclusions — used to detect session leakage across conversations.
    absent_exclusions: list[str] = field(default_factory=list)
    # Expected tool calls, e.g. [{"tool": "SimilarTool",
    # "args_contain": {"items": "$S.shown_items.1"}}]. "$S.<path>" values are
    # resolved against the turn's post-turn session_state; a list arg matches
    # when it CONTAINS the resolved value, scalars must be equal.
    expected_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    # Negative expectations (previously unscoreable):
    #   expect_clarification -> turn passes iff the agent asked a question
    #     (executor.last_question non-empty) instead of guessing;
    #   expect_no_result     -> turn passes iff the agent returned zero items
    #     (e.g. filters that match nothing) instead of inventing recommendations.
    expect_clarification: bool = False
    expect_no_result: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "turn_id": self.turn_id,
            "position": self.position,
            "user_request": self.user_request,
            "expected_state": self.expected_state,
            "expected_behavior": self.expected_behavior,
            "expected_items": self.expected_items,
            "expected_exclusions": self.expected_exclusions,
            "absent_exclusions": self.absent_exclusions,
            "expected_tool_calls": self.expected_tool_calls,
            "expect_clarification": self.expect_clarification,
            "expect_no_result": self.expect_no_result,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TurnInput":
        """Create from dict."""
        return cls(
            turn_id=data["turn_id"],
            position=data["position"],
            user_request=data["user_request"],
            expected_state=data.get("expected_state", {}),
            expected_behavior=data.get("expected_behavior", ""),
            expected_items=data.get("expected_items", []),
            expected_exclusions=data.get("expected_exclusions", {}),
            absent_exclusions=data.get("absent_exclusions", []),
            expected_tool_calls=data.get("expected_tool_calls", []),
            expect_clarification=bool(data.get("expect_clarification", False)),
            expect_no_result=bool(data.get("expect_no_result", False)),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TurnResult:
    """Result of evaluating a single turn.

    Attributes:
        turn_id: The turn ID that was evaluated
        actual_items: Items actually recommended
        actual_exclusions: Items/categories actually excluded
        session_state: Session state after the turn
        success: Whether the turn executed without errors
        error: Error message if success=False
        metrics: Turn-level metrics
        latency_seconds: Time taken for this turn
        trace: Execution trace (steps, tool calls, etc.)
    """
    turn_id: str
    actual_items: list[str] = field(default_factory=list)
    actual_exclusions: dict[str, list[str]] = field(default_factory=dict)
    session_state: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: str | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    latency_seconds: float = 0.0
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "turn_id": self.turn_id,
            "actual_items": self.actual_items,
            "actual_exclusions": self.actual_exclusions,
            "session_state": self.session_state,
            "success": self.success,
            "error": self.error,
            "metrics": self.metrics,
            "latency_seconds": self.latency_seconds,
            "trace": self.trace,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TurnResult":
        """Create from dict."""
        return cls(
            turn_id=data["turn_id"],
            actual_items=data.get("actual_items", []),
            actual_exclusions=data.get("actual_exclusions", {}),
            session_state=data.get("session_state", {}),
            success=data.get("success", True),
            error=data.get("error"),
            metrics=data.get("metrics", {}),
            latency_seconds=data.get("latency_seconds", 0.0),
            trace=data.get("trace", {}),
        )


@dataclass
class Conversation:
    """A multi-turn conversation with evaluation metadata.

    Attributes:
        conversation_id: Unique identifier for this conversation
        user_id: User/session identity (if applicable)
        turns: List of turn inputs
        initial_context: Initial context before first turn
        expected_outcome: Expected overall conversation outcome
        tags: Tags for categorization
        metadata: Additional metadata
    """
    conversation_id: str
    user_id: str | None = None
    turns: list[TurnInput] = field(default_factory=list)
    initial_context: dict[str, Any] = field(default_factory=dict)
    expected_outcome: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "turns": [t.to_dict() for t in self.turns],
            "initial_context": self.initial_context,
            "expected_outcome": self.expected_outcome,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Conversation":
        """Create from dict."""
        return cls(
            conversation_id=data["conversation_id"],
            user_id=data.get("user_id"),
            turns=[TurnInput.from_dict(t) for t in data.get("turns", [])],
            initial_context=data.get("initial_context", {}),
            expected_outcome=data.get("expected_outcome", ""),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ConversationResult:
    """Result of evaluating a full conversation.

    Attributes:
        conversation_id: The conversation ID that was evaluated
        turn_results: List of individual turn results
        conversation_success: Whether the conversation succeeded overall
        failure_stage: Stage where conversation failed (if applicable)
        error: Error message if conversation failed
        metrics: Conversation-level metrics
        latency_seconds: Total time for the conversation
        token_usage: Token usage across all turns
        timestamp: ISO timestamp of evaluation
        git_sha: Git commit SHA
    """
    conversation_id: str
    turn_results: list[TurnResult] = field(default_factory=list)
    conversation_success: bool = True
    failure_stage: str | None = None
    error: str | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    latency_seconds: float = 0.0
    token_usage: dict[str, int] | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    git_sha: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "conversation_id": self.conversation_id,
            "turn_results": [t.to_dict() for t in self.turn_results],
            "conversation_success": self.conversation_success,
            "failure_stage": self.failure_stage,
            "error": self.error,
            "metrics": self.metrics,
            "latency_seconds": self.latency_seconds,
            "token_usage": self.token_usage,
            "timestamp": self.timestamp,
            "git_sha": self.git_sha,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConversationResult":
        """Create from dict."""
        return cls(
            conversation_id=data["conversation_id"],
            turn_results=[TurnResult.from_dict(t) for t in data.get("turn_results", [])],
            conversation_success=data.get("conversation_success", True),
            failure_stage=data.get("failure_stage"),
            error=data.get("error"),
            metrics=data.get("metrics", {}),
            latency_seconds=data.get("latency_seconds", 0.0),
            token_usage=data.get("token_usage"),
            timestamp=data.get("timestamp"),
            git_sha=data.get("git_sha", ""),
            provenance=data.get("provenance", {}),
        )

    def compute_hash(self) -> str:
        """Compute a hash of the conversation configuration for reproducibility."""
        hash_input = {
            "conversation_id": self.conversation_id,
            "turns": [t.to_dict() for t in self.turn_results],
            "provenance": self.provenance,
        }
        return hashlib.sha256(json.dumps(hash_input, sort_keys=True).encode()).hexdigest()[:16]


@dataclass
class ConversationSummary:
    """Summary of multiple conversation evaluations.

    Attributes:
        multi_turn_version: Version of the multi-turn schema
        total_conversations: Number of conversations evaluated
        turn_success_rate: Overall turn success rate
        conversation_success_rate: Overall conversation success rate
        metrics: Aggregated metrics
        latency: Latency statistics
        failure_distribution: Distribution of failure stages
        context_retention_metrics: Context retention and update metrics
        timestamp: ISO timestamp
        git_sha: Git commit SHA
    """
    multi_turn_version: str = MULTI_TURN_VERSION
    total_conversations: int = 0
    turn_success_rate: float = 0.0
    conversation_success_rate: float = 0.0
    # Turn-count fields: scheduled = turns defined in the dataset; executed =
    # turns actually run (turns after a failure are never executed). The gap
    # between them is the "gave up early" signal. avg_turns_per_conversation
    # uses EXECUTED turns; turn_completion_ratio = executed / scheduled.
    total_turns_scheduled: int = 0
    total_turns_executed: int = 0
    avg_turns_per_conversation: float | None = None
    turn_completion_ratio: float | None = None
    failed_conversation_ids: list[str] = field(default_factory=list)
    failed_conversations: int = 0
    metrics: dict[str, float] = field(default_factory=dict)
    latency: dict[str, float] = field(default_factory=dict)
    failure_distribution: dict[str, int] = field(default_factory=dict)
    context_retention_metrics: dict[str, float] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    git_sha: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "multi_turn_version": self.multi_turn_version,
            "total_conversations": self.total_conversations,
            "turn_success_rate": self.turn_success_rate,
            "conversation_success_rate": self.conversation_success_rate,
            "total_turns_scheduled": self.total_turns_scheduled,
            "total_turns_executed": self.total_turns_executed,
            "avg_turns_per_conversation": self.avg_turns_per_conversation,
            "turn_completion_ratio": self.turn_completion_ratio,
            "failed_conversation_ids": self.failed_conversation_ids,
            "failed_conversations": self.failed_conversations,
            "metrics": self.metrics,
            "latency": self.latency,
            "failure_distribution": self.failure_distribution,
            "context_retention_metrics": self.context_retention_metrics,
            "timestamp": self.timestamp,
            "git_sha": self.git_sha,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConversationSummary":
        """Create from dict."""
        return cls(
            multi_turn_version=data.get("multi_turn_version", MULTI_TURN_VERSION),
            total_conversations=data.get("total_conversations", 0),
            turn_success_rate=data.get("turn_success_rate", 0.0),
            conversation_success_rate=data.get("conversation_success_rate", 0.0),
            total_turns_scheduled=data.get("total_turns_scheduled", 0),
            total_turns_executed=data.get("total_turns_executed", 0),
            avg_turns_per_conversation=data.get("avg_turns_per_conversation"),
            turn_completion_ratio=data.get("turn_completion_ratio"),
            failed_conversation_ids=data.get("failed_conversation_ids", []),
            failed_conversations=data.get("failed_conversations", 0),
            metrics=data.get("metrics", {}),
            latency=data.get("latency", {}),
            failure_distribution=data.get("failure_distribution", {}),
            context_retention_metrics=data.get("context_retention_metrics", {}),
            timestamp=data.get("timestamp"),
            git_sha=data.get("git_sha", ""),
        )
