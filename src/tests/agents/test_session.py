"""Tests for Session class managing multi-turn conversation state."""

import pytest

from package.agents.session import Session


def test_session_initial_state():
    """Test that a new session starts with empty state."""
    session = Session()
    assert session.turns == []
    assert session.shown_items == []
    assert session.candidates == []
    assert session.ranked == []
    assert session.constraints == {}
    assert session.feedback == {}
    assert session.get_valid_ids() == set()


def test_session_add_turn():
    """Test adding a turn to the session."""
    session = Session()
    session.add_turn("test request", "test plan", "test answer")

    assert len(session.turns) == 1
    assert session.turns[0].user_request == "test request"
    assert session.turns[0].plan == "test plan"
    assert session.turns[0].answer_summary == "test answer"


def test_session_turn_truncation():
    """Test that old turns are removed when max_turns is exceeded."""
    session = Session(max_turns=3)

    for i in range(5):
        session.add_turn(f"request {i}", f"plan {i}", f"answer {i}")

    # Should only keep the last 3 turns
    assert len(session.turns) == 3
    assert session.turns[0].user_request == "request 2"
    assert session.turns[1].user_request == "request 3"
    assert session.turns[2].user_request == "request 4"


def test_session_answer_truncation():
    """Test that long answers are truncated to max_turn_chars."""
    session = Session(max_turn_chars=10)
    long_answer = "a" * 20

    session.add_turn("request", "plan", long_answer)

    assert len(session.turns[0].answer_summary) == 10
    assert session.turns[0].answer_summary == "aaaaaaaaaa"


def test_session_add_shown_items():
    """Test adding items to the shown list."""
    session = Session()
    session.add_shown_items(["item1", "item2", "item3"])

    assert session.shown_items == ["item1", "item2", "item3"]


def test_session_shown_items_limit():
    """Test that old shown items are removed when max_shown_items is exceeded."""
    session = Session(max_shown_items=3)

    session.add_shown_items(["item1", "item2"])
    session.add_shown_items(["item3", "item4"])

    # Should only keep the last 3 items
    assert session.shown_items == ["item2", "item3", "item4"]


def test_session_set_candidates():
    """Test setting candidates for the current turn."""
    session = Session()
    session.set_candidates(["c1", "c2", "c3"], ["r1", "r2"])

    assert session.candidates == ["c1", "c2", "c3"]
    assert session.ranked == ["r1", "r2"]


def test_session_candidates_limit():
    """Test that candidates are limited to max_candidates."""
    session = Session(max_candidates=2)
    session.set_candidates(["c1", "c2", "c3"], ["r1", "r2", "r3"])

    assert session.candidates == ["c1", "c2"]
    assert session.ranked == ["r1", "r2"]


def test_session_update_constraints():
    """Test updating session constraints."""
    session = Session()
    session.update_constraints({"price_max": 100})
    session.update_constraints({"category": "Action"})

    assert session.constraints == {"price_max": 100, "category": "Action"}


def test_session_add_exclusions():
    """Test adding item and category exclusions."""
    session = Session()
    session.add_exclusions(item_ids=["item1", "item2"], categories=["Action"])

    assert session.constraints["exclude_item_ids"] == ["item1", "item2"]
    assert session.constraints["exclude_categories"] == ["Action"]


def test_session_add_feedback():
    """Test recording user feedback on items."""
    session = Session()
    session.add_feedback("item1", "like")
    session.add_feedback("item2", "dislike")

    assert session.feedback == {"item1": "like", "item2": "dislike"}


def test_session_get_valid_ids():
    """Test that get_valid_ids returns all IDs from shown, candidates, and ranked."""
    session = Session()
    session.add_shown_items(["s1", "s2"])
    session.set_candidates(["c1", "c2"], ["r1", "r2"])

    valid_ids = session.get_valid_ids()
    assert valid_ids == {"s1", "s2", "c1", "c2", "r1", "r2"}


def test_session_reset():
    """Test resetting the session to initial state."""
    session = Session()
    session.add_turn("request", "plan", "answer")
    session.add_shown_items(["item1"])
    session.set_candidates(["c1"], ["r1"])
    session.update_constraints({"price_max": 100})
    session.add_feedback("item1", "like")

    session.reset()

    assert session.turns == []
    assert session.shown_items == []
    assert session.candidates == []
    assert session.ranked == []
    assert session.constraints == {}
    assert session.feedback == {}
    assert session.get_valid_ids() == set()


def test_session_to_dict():
    """Test converting session to dictionary for prompt injection."""
    session = Session()
    session.add_shown_items(["s1", "s2"])
    session.set_candidates(["c1"], ["r1"])
    session.update_constraints({"price_max": 100})

    session_dict = session.to_dict()

    assert session_dict["turns_count"] == 0
    assert session_dict["shown_items"] == ["s1", "s2"]
    assert session_dict["candidates"] == ["c1"]
    assert session_dict["ranked"] == ["r1"]
    assert session_dict["constraints"] == {"price_max": 100}
    assert session_dict["feedback"] == {}


def test_session_repr():
    """Test session string representation."""
    session = Session()
    session.add_turn("request", "plan", "answer")
    session.add_shown_items(["s1", "s2"])

    repr_str = repr(session)
    assert "turns=1" in repr_str
    assert "shown=2" in repr_str
