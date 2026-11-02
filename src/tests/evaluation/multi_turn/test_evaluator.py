"""Tests for multi-turn conversation evaluation."""

import pytest

from package.evaluation.multi_turn import (
    TurnInput,
    TurnResult,
    Conversation,
    ConversationResult,
    ConversationSummary,
    MultiTurnEvaluator,
)


def test_turn_input_serialization():
    """Test TurnInput serialization round-trip."""
    turn_input = TurnInput(
        turn_id="test_t1",
        position=0,
        user_request="Test request",
        expected_behavior="Test behavior",
        expected_items=["item1", "item2"],
        metadata={"scenario": "test"},
    )

    data = turn_input.to_dict()
    restored = TurnInput.from_dict(data)

    assert restored.turn_id == turn_input.turn_id
    assert restored.position == turn_input.position
    assert restored.user_request == turn_input.user_request
    assert restored.expected_items == turn_input.expected_items


def test_conversation_serialization():
    """Test Conversation serialization round-trip."""
    conversation = Conversation(
        conversation_id="conv_001",
        user_id="user_001",
        turns=[
            TurnInput(
                turn_id="t1",
                position=0,
                user_request="Turn 1",
                expected_behavior="Behavior 1",
            ),
            TurnInput(
                turn_id="t2",
                position=1,
                user_request="Turn 2",
                expected_behavior="Behavior 2",
            ),
        ],
        initial_context={"key": "value"},
        expected_outcome="Success",
        tags=["multi_turn"],
        metadata={"scenario": "test"},
    )

    data = conversation.to_dict()
    restored = Conversation.from_dict(data)

    assert restored.conversation_id == conversation.conversation_id
    assert len(restored.turns) == 2
    assert restored.initial_context == conversation.initial_context


def test_conversation_result_serialization():
    """Test ConversationResult serialization round-trip."""
    result = ConversationResult(
        conversation_id="conv_001",
        turn_results=[
            TurnResult(
                turn_id="t1",
                actual_items=["item1"],
                success=True,
                metrics={"item_match_rate": 1.0},
            ),
        ],
        conversation_success=True,
        metrics={"turn_success_rate": 1.0},
    )

    data = result.to_dict()
    restored = ConversationResult.from_dict(data)

    assert restored.conversation_id == result.conversation_id
    assert len(restored.turn_results) == 1
    assert restored.conversation_success == result.conversation_success


def test_conversation_summary_serialization():
    """Test ConversationSummary serialization round-trip."""
    summary = ConversationSummary(
        total_conversations=10,
        turn_success_rate=0.95,
        conversation_success_rate=0.90,
        metrics={"avg_item_match_rate": 0.85},
        latency={"mean": 1.0},
    )

    data = summary.to_dict()
    restored = ConversationSummary.from_dict(data)

    assert restored.total_conversations == summary.total_conversations
    assert restored.turn_success_rate == summary.turn_success_rate


def test_multi_turn_evaluator_turn_scoring():
    """Test turn-level scoring."""
    evaluator = MultiTurnEvaluator()

    turn_input = TurnInput(
        turn_id="test_t1",
        position=0,
        user_request="Test",
        expected_items=["item1", "item2"],
    )

    # Simulate successful turn with matching items
    turn_output = {"items": ["item1", "item2"], "exclusions": {}}
    session_state = {"shown_items": [], "constraints": {}}

    metrics = evaluator._score_turn(turn_input, turn_output, session_state)

    assert metrics["turn_success"] == 1.0
    assert metrics["item_match_rate"] == 1.0
    assert metrics["exclusion_compliance"] == 1.0


def test_multi_turn_evaluator_conversation_metrics():
    """Test conversation-level metrics calculation."""
    evaluator = MultiTurnEvaluator()

    conversation = Conversation(
        conversation_id="conv_001",
        turns=[
            TurnInput(
                turn_id="t1",
                position=0,
                user_request="Turn 1",
                expected_items=["item1"],
            ),
            TurnInput(
                turn_id="t2",
                position=1,
                user_request="Turn 2",
                expected_items=["item2"],
            ),
        ],
    )

    # Mock turn results
    turn_results = [
        TurnResult(
            turn_id="t1",
            actual_items=["item1"],
            success=True,
            metrics={"item_match_rate": 1.0, "exclusion_compliance": 1.0},
            session_state={"shown_items": ["item1"], "constraints": {}},
        ),
        TurnResult(
            turn_id="t2",
            actual_items=["item2"],
            success=True,
            metrics={"item_match_rate": 1.0, "exclusion_compliance": 1.0},
            session_state={"shown_items": ["item1", "item2"], "constraints": {}},
        ),
    ]

    metrics = evaluator._calculate_conversation_metrics(turn_results, conversation)

    assert metrics["turn_success_rate"] == 1.0
    assert metrics["conversation_success"] == 1.0
    assert metrics["avg_item_match_rate"] == 1.0
    assert metrics["context_retention"] == 1.0


def test_session_isolation():
    """Test that two independent conversations do not share session state."""
    # This is a unit test for the concept; actual session isolation is tested in test_session.py
    session1 = {"turns": [], "shown_items": [], "constraints": {}}
    session2 = {"turns": [], "shown_items": [], "constraints": {}}

    session1["shown_items"] = ["item1"]
    session2["shown_items"] = ["item2"]

    assert session1["shown_items"] == ["item1"]
    assert session2["shown_items"] == ["item2"]
    assert session1["shown_items"] != session2["shown_items"]


def test_context_retention_detection():
    """Test that context retention is detected correctly."""
    evaluator = MultiTurnEvaluator()

    conversation = Conversation(
        conversation_id="conv_001",
        turns=[
            TurnInput(
                turn_id="t1",
                position=0,
                user_request="Turn 1",
                expected_items=["item1"],
            ),
            TurnInput(
                turn_id="t2",
                position=1,
                user_request="Turn 2",
                expected_items=["item2"],
            ),
        ],
    )

    # Test monotonic growth (should pass)
    turn_results_monotonic = [
        TurnResult(
            turn_id="t1",
            actual_items=["item1"],
            success=True,
            metrics={},
            session_state={"shown_items": ["item1"], "constraints": {}},
        ),
        TurnResult(
            turn_id="t2",
            actual_items=["item1", "item2"],
            success=True,
            metrics={},
            session_state={"shown_items": ["item1", "item2"], "constraints": {}},
        ),
    ]

    metrics = evaluator._calculate_conversation_metrics(turn_results_monotonic, conversation)
    assert metrics["context_retention"] == 1.0

    # Test non-monotonic (should fail)
    turn_results_non_monotonic = [
        TurnResult(
            turn_id="t1",
            actual_items=["item1", "item2"],
            success=True,
            metrics={},
            session_state={"shown_items": ["item1", "item2"], "constraints": {}},
        ),
        TurnResult(
            turn_id="t2",
            actual_items=["item1"],
            success=True,
            metrics={},
            session_state={"shown_items": ["item1"], "constraints": {}},
        ),
    ]

    metrics = evaluator._calculate_conversation_metrics(turn_results_non_monotonic, conversation)
    assert metrics["context_retention"] == 0.0
