"""Multi-turn evaluation tests using the existing session infrastructure."""

import pytest

from package.agents.session import Session
from package.evaluation.multi_turn import (
    Conversation,
    TurnInput,
    MultiTurnEvaluator,
)


def test_session_isolation_with_real_session():
    """Test that two Session objects do not share state."""
    session1 = Session()
    session2 = Session()

    session1.add_shown_items(["item1"])
    session2.add_shown_items(["item2"])

    assert session1.shown_items == ["item1"]
    assert session2.shown_items == ["item2"]
    assert session1.get_valid_ids() == {"item1"}
    assert session2.get_valid_ids() == {"item2"}


def test_session_context_retention():
    """Test that session retains context across turns."""
    session = Session()

    # Turn 1
    session.add_shown_items(["item1", "item2"])
    session.update_constraints({"price_max": 50})

    assert len(session.shown_items) == 2
    assert session.constraints["price_max"] == 50

    # Turn 2
    session.add_shown_items(["item3"])
    session.update_constraints({"category": "Action"})

    assert len(session.shown_items) == 3
    assert session.constraints["price_max"] == 50
    assert session.constraints["category"] == "Action"


def test_session_exclusion_persistence():
    """Test that exclusions persist across turns."""
    session = Session()

    # Turn 1: Add exclusion
    session.add_exclusions(item_ids=["item1"], categories=["Puzzle"])

    assert "item1" in session.constraints["exclude_item_ids"]
    assert "Puzzle" in session.constraints["exclude_categories"]

    # Turn 2: Add more exclusions
    session.add_exclusions(item_ids=["item2"])

    assert "item1" in session.constraints["exclude_item_ids"]
    assert "item2" in session.constraints["exclude_item_ids"]
    assert "Puzzle" in session.constraints["exclude_categories"]


def test_conversation_with_real_session():
    """Test that the evaluator works with real Session objects."""
    conversation = Conversation(
        conversation_id="conv_test",
        turns=[
            TurnInput(
                turn_id="t1",
                position=0,
                user_request="Show me games",
                expected_items=["item1", "item2"],
            ),
            TurnInput(
                turn_id="t2",
                position=1,
                user_request="Show me more",
                expected_items=["item3", "item4"],
            ),
        ],
    )

    # Mock agent runner that uses real Session
    class SessionAwareAgentRunner:
        def __init__(self):
            pass

        def run_turn(self, turn_input, session):
            # Simulate agent behavior
            if turn_input.position == 0:
                session.add_shown_items(["item1", "item2"])
                return {"items": ["item1", "item2"], "exclusions": {}}
            elif turn_input.position == 1:
                session.add_shown_items(["item3", "item4"])
                return {"items": ["item3", "item4"], "exclusions": {}}

    evaluator = MultiTurnEvaluator()
    # Override session initialization to use real Session
    original_init = evaluator._initialize_session
    evaluator._initialize_session = lambda ctx: Session()

    agent_runner = SessionAwareAgentRunner()
    result = evaluator.evaluate_conversation(conversation, agent_runner)

    assert result.conversation_success
    assert len(result.turn_results) == 2
    assert result.turn_results[0].success
    assert result.turn_results[1].success
    assert result.metrics["context_retention"] == 1.0


def test_multi_turn_m1_price_refinement_scenario():
    """Test M1: Price refinement scenario with real session."""
    conversation = Conversation(
        conversation_id="conv_m1",
        turns=[
            TurnInput(
                turn_id="m1_t1",
                position=0,
                user_request="Show me video games",
                expected_items=["vg_a", "vg_b", "vg_c"],
                metadata={"scenario": "M1"},
            ),
            TurnInput(
                turn_id="m1_t2",
                position=1,
                user_request="Show me cheaper ones under $50",
                expected_items=["vg_a"],
                expected_exclusions={"price_max": 50},
                metadata={"scenario": "M1"},
            ),
        ],
    )

    class M1AgentRunner:
        def run_turn(self, turn_input, session):
            if turn_input.position == 0:
                session.add_shown_items(["vg_a", "vg_b", "vg_c"])
                return {"items": ["vg_a", "vg_b", "vg_c"], "exclusions": {}}
            elif turn_input.position == 1:
                session.update_constraints({"price_max": 50})
                session.add_shown_items(["vg_a"])
                return {"items": ["vg_a"], "exclusions": {"price_max": 50}}

    evaluator = MultiTurnEvaluator()
    evaluator._initialize_session = lambda ctx: Session()

    agent_runner = M1AgentRunner()
    result = evaluator.evaluate_conversation(conversation, agent_runner)

    assert result.conversation_success
    assert result.metrics["turn_success_rate"] == 1.0
    assert result.metrics["conversation_success"] == 1.0


def test_multi_turn_m3_exclusion_scenario():
    """Test M3: Exclusion persistence scenario."""
    conversation = Conversation(
        conversation_id="conv_m3",
        turns=[
            TurnInput(
                turn_id="m3_t1",
                position=0,
                user_request="Show me video games",
                expected_items=["vg_a", "vg_b", "vg_c"],
                metadata={"scenario": "M3"},
            ),
            TurnInput(
                turn_id="m3_t2",
                position=1,
                user_request="I don't like the first one, show me others",
                expected_items=["vg_d", "vg_e"],
                expected_exclusions={"exclude_item_ids": ["vg_a"]},
                metadata={"scenario": "M3"},
            ),
        ],
    )

    class M3AgentRunner:
        def run_turn(self, turn_input, session):
            if turn_input.position == 0:
                session.add_shown_items(["vg_a", "vg_b", "vg_c"])
                return {"items": ["vg_a", "vg_b", "vg_c"], "exclusions": {}}
            elif turn_input.position == 1:
                session.add_exclusions(item_ids=["vg_a"])
                session.add_shown_items(["vg_d", "vg_e"])
                return {"items": ["vg_d", "vg_e"], "exclusions": {"exclude_item_ids": ["vg_a"]}}

    evaluator = MultiTurnEvaluator()
    evaluator._initialize_session = lambda ctx: Session()

    agent_runner = M3AgentRunner()
    result = evaluator.evaluate_conversation(conversation, agent_runner)

    assert result.conversation_success
    assert result.metrics["exclusion_compliance"] == 1.0


def test_multi_turn_m4_more_items_scenario():
    """Test M4: More items without repetition."""
    conversation = Conversation(
        conversation_id="conv_m4",
        turns=[
            TurnInput(
                turn_id="m4_t1",
                position=0,
                user_request="Show me video games",
                expected_items=["vg_a", "vg_b", "vg_c"],
                metadata={"scenario": "M4"},
            ),
            TurnInput(
                turn_id="m4_t2",
                position=1,
                user_request="Show me more",
                expected_items=["vg_d", "vg_e", "vg_f"],
                expected_exclusions={"exclude_item_ids": ["vg_a", "vg_b", "vg_c"]},
                metadata={"scenario": "M4"},
            ),
        ],
    )

    class M4AgentRunner:
        def run_turn(self, turn_input, session):
            if turn_input.position == 0:
                session.add_shown_items(["vg_a", "vg_b", "vg_c"])
                return {"items": ["vg_a", "vg_b", "vg_c"], "exclusions": {}}
            elif turn_input.position == 1:
                # Exclude shown items
                session.add_exclusions(item_ids=session.shown_items)
                session.add_shown_items(["vg_d", "vg_e", "vg_f"])
                return {"items": ["vg_d", "vg_e", "vg_f"], "exclusions": {"exclude_item_ids": session.shown_items}}

    evaluator = MultiTurnEvaluator()
    evaluator._initialize_session = lambda ctx: Session()

    agent_runner = M4AgentRunner()
    result = evaluator.evaluate_conversation(conversation, agent_runner)

    assert result.conversation_success
    assert result.metrics["context_retention"] == 1.0


def test_conversation_failure_propagates():
    """Test that a failed turn causes conversation failure."""
    conversation = Conversation(
        conversation_id="conv_fail",
        turns=[
            TurnInput(
                turn_id="t1",
                position=0,
                user_request="Valid request",
                expected_items=["item1"],
            ),
            TurnInput(
                turn_id="t2",
                position=1,
                user_request="Invalid request",
                expected_items=[],
            ),
        ],
    )

    class FailingAgentRunner:
        def run_turn(self, turn_input, session):
            if turn_input.position == 0:
                session.add_shown_items(["item1"])
                return {"items": ["item1"], "exclusions": {}}
            elif turn_input.position == 1:
                raise ValueError("Simulated error")

    evaluator = MultiTurnEvaluator()
    evaluator._initialize_session = lambda ctx: Session()

    agent_runner = FailingAgentRunner()
    result = evaluator.evaluate_conversation(conversation, agent_runner)

    assert not result.conversation_success
    assert result.failure_stage == "turn_1"
    assert result.error == "Simulated error"
    assert result.turn_results[0].success
    assert not result.turn_results[1].success
