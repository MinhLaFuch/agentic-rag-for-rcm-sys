"""Session state for multi-turn conversations.

Manages turn history, shown items, candidates, and constraints across conversation turns.
All state is mutable and updated deterministically after each turn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Turn:
    """A single turn in the conversation."""
    user_request: str
    plan: str
    answer_summary: str  # Truncated summary of the agent's response


@dataclass
class Session:
    """Session state for multi-turn conversations.

    All fields are public and read-only from the planner's perspective.
    The agent updates the session after each turn using update_session().
    """

    # Turn history (limited by max_turns)
    turns: list[Turn] = field(default_factory=list)

    # Items shown to the user, in order (limited by max_shown_items)
    shown_items: list[str] = field(default_factory=list)

    # Candidates from the most recent turn (limited by max_candidates)
    candidates: list[str] = field(default_factory=list)
    ranked: list[str] = field(default_factory=list)

    # Current constraints (expectations) from the session
    constraints: dict[str, Any] = field(default_factory=dict)

    # Feedback on items (likes/dislikes within the session)
    feedback: dict[str, str] = field(default_factory=dict)  # item_id -> "like"|"dislike"

    # Limits (from config)
    max_turns: int = 10
    max_shown_items: int = 50
    max_candidates: int = 100
    max_turn_chars: int = 500

    def add_turn(self, user_request: str, plan: str, answer: str) -> None:
        """Add a new turn to the session, respecting limits."""
        # Truncate answer summary if needed
        answer_summary = answer[:self.max_turn_chars] if len(answer) > self.max_turn_chars else answer

        turn = Turn(
            user_request=user_request,
            plan=plan,
            answer_summary=answer_summary
        )

        self.turns.append(turn)

        # Enforce max_turns limit (FIFO)
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]

    def add_shown_items(self, items: list[str]) -> None:
        """Add items to the shown list, respecting max_shown_items limit."""
        self.shown_items.extend(items)

        # Enforce max_shown_items limit (FIFO)
        if len(self.shown_items) > self.max_shown_items:
            self.shown_items = self.shown_items[-self.max_shown_items:]

    def set_candidates(self, candidates: list[str], ranked: list[str]) -> None:
        """Set the candidates for the current turn, respecting max_candidates limit."""
        self.candidates = candidates[:self.max_candidates]
        self.ranked = ranked[:self.max_candidates]

    def update_constraints(self, new_constraints: dict[str, Any]) -> None:
        """Update session constraints with new values."""
        self.constraints.update(new_constraints)

    def add_exclusions(self, item_ids: list[str] | None = None, categories: list[str] | None = None) -> None:
        """Add items/categories to exclusion constraints."""
        if "exclude_item_ids" not in self.constraints:
            self.constraints["exclude_item_ids"] = []
        if "exclude_categories" not in self.constraints:
            self.constraints["exclude_categories"] = []

        if item_ids:
            self.constraints["exclude_item_ids"].extend(item_ids)
        if categories:
            self.constraints["exclude_categories"].extend(categories)

    def add_feedback(self, item_id: str, sentiment: str) -> None:
        """Record user feedback on an item."""
        self.feedback[item_id] = sentiment

    def get_valid_ids(self) -> set[str]:
        """Return all item IDs that are valid for reference in this session.

        Valid IDs = shown_items ∪ candidates ∪ ranked
        """
        valid = set(self.shown_items) | set(self.ranked)
        # candidates might be dicts (from SQLTool), extract item_id if needed
        for c in self.candidates:
            if isinstance(c, dict) and "item_id" in c:
                valid.add(c["item_id"])
            elif isinstance(c, str):
                valid.add(c)
        return valid

    def reset(self) -> None:
        """Reset the session to initial state."""
        self.turns.clear()
        self.shown_items.clear()
        self.candidates.clear()
        self.ranked.clear()
        self.constraints.clear()
        self.feedback.clear()

    def to_dict(self) -> dict[str, Any]:
        """Convert session to a dictionary for prompt injection."""
        return {
            "turns_count": len(self.turns),
            "shown_items": self.shown_items,
            "candidates": self.candidates,
            "ranked": self.ranked,
            "constraints": self.constraints,
            "feedback": self.feedback,
        }

    def __repr__(self) -> str:
        return f"Session(turns={len(self.turns)}, shown={len(self.shown_items)}, candidates={len(self.candidates)})"
