"""Column schema for the raw Amazon review tables (replaces `_config.py`)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColumnSchema:
    """Immutable, named replacement for the old `get_config() -> (list, list)` tuple."""

    required: tuple[str, ...] = ("user_id", "parent_asin", "rating", "timestamp")
    optional: tuple[str, ...] = ("title", "text", "helpful_vote", "verified_purchase")

    @property
    def all(self) -> tuple[str, ...]:
        return self.required + self.optional


REVIEW_SCHEMA = ColumnSchema()