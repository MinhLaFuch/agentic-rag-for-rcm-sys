"""Test classify_outcome behavior."""

from package.inference.outcome.classify_outcome import classify_outcome
from package.inference._dataclass import AgentOutcome


def test_ask_user_status():
    """question with n_steps=0 → ask_user."""
    outcome = AgentOutcome(
        request_text="test",
        items=[],
        question="Which product?",
        errors=[],
        invented_ids=[],
        cold_start=None,
        n_steps=0,
    )
    status, reason = classify_outcome(outcome)
    assert status == "ask_user"
    assert reason is None


def test_tool_error_invented_ids():
    """invented_ids present → tool_error with invented ids in reason."""
    outcome = AgentOutcome(
        request_text="test",
        items=[],
        question=None,
        errors=[],
        invented_ids=["fake_id"],
        cold_start=None,
        n_steps=1,
    )
    status, reason = classify_outcome(outcome)
    assert status == "tool_error"
    assert "invented ids" in reason
    assert "fake_id" in reason


def test_tool_error_planner_error():
    """planner error in errors → tool_error with planner error in reason."""
    outcome = AgentOutcome(
        request_text="test",
        items=[],
        question=None,
        errors=[{"tool": "planner", "error": "LLM failed"}],
        invented_ids=[],
        cold_start=None,
        n_steps=0,
    )
    status, reason = classify_outcome(outcome)
    assert status == "tool_error"
    assert "planner" in reason
    assert "LLM failed" in reason


def test_ok_with_items():
    """items present → ok."""
    outcome = AgentOutcome(
        request_text="test",
        items=[{"item_id": "item1"}],
        question=None,
        errors=[],
        invented_ids=[],
        cold_start=None,
        n_steps=1,
    )
    status, reason = classify_outcome(outcome)
    assert status == "ok"
    assert reason is None


def test_ok_partial_with_failed_tool():
    """items present with errors → ok with 'partial: <tool> failed' in reason."""
    outcome = AgentOutcome(
        request_text="test",
        items=[{"item_id": "item1"}],
        question=None,
        errors=[{"tool": "SQLTool", "error": "timeout"}],
        invented_ids=[],
        cold_start=None,
        n_steps=2,
    )
    status, reason = classify_outcome(outcome)
    assert status == "ok"
    assert "partial" in reason
    assert "SQLTool" in reason
    assert "failed" in reason


def test_tool_error_no_items_with_errors():
    """no items with errors → tool_error."""
    outcome = AgentOutcome(
        request_text="test",
        items=[],
        question=None,
        errors=[{"tool": "SQLTool", "error": "timeout"}],
        invented_ids=[],
        cold_start=None,
        n_steps=1,
    )
    status, reason = classify_outcome(outcome)
    assert status == "tool_error"
    assert "SQLTool" in reason
    assert "timeout" in reason


def test_no_result_no_items_no_errors():
    """no items, no errors → no_result."""
    outcome = AgentOutcome(
        request_text="test",
        items=[],
        question=None,
        errors=[],
        invented_ids=[],
        cold_start=None,
        n_steps=1,
    )
    status, reason = classify_outcome(outcome)
    assert status == "no_result"
    assert "no items returned" in reason


def test_question_with_steps_ignored():
    """question with steps → reason contains 'question ignored'."""
    outcome = AgentOutcome(
        request_text="test",
        items=[{"item_id": "item1"}],
        question="Which product?",
        errors=[],
        invented_ids=[],
        cold_start=None,
        n_steps=1,
    )
    status, reason = classify_outcome(outcome)
    assert status == "ok"
    assert "question ignored" in reason


def test_cold_start_flag_in_no_result():
    """cold_start=True in no_result reason."""
    outcome = AgentOutcome(
        request_text="test",
        items=[],
        question=None,
        errors=[],
        invented_ids=[],
        cold_start=True,
        n_steps=1,
    )
    status, reason = classify_outcome(outcome)
    assert status == "no_result"
    assert "cold_start" in reason


def test_multiple_failed_tools_in_partial():
    """Multiple failed tools → all listed in partial reason."""
    outcome = AgentOutcome(
        request_text="test",
        items=[{"item_id": "item1"}],
        question=None,
        errors=[
            {"tool": "SQLTool", "error": "timeout"},
            {"tool": "QueryTool", "error": "not found"},
        ],
        invented_ids=[],
        cold_start=None,
        n_steps=3,
    )
    status, reason = classify_outcome(outcome)
    assert status == "ok"
    assert "partial" in reason
    assert "SQLTool" in reason
    assert "QueryTool" in reason
