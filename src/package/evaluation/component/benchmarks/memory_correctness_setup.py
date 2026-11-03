"""Compatibility module for memory_correctness_setup."""

from __future__ import annotations

from .create_test_interactions import create_test_interactions
from .create_test_corpus import create_test_corpus
from .create_test_meta import create_test_meta
from .create_test_mappings import create_test_mappings
from .get_interactions_without_rating import get_interactions_without_rating

__all__ = [
    "create_test_interactions",
    "create_test_corpus",
    "create_test_meta",
    "create_test_mappings",
    "get_interactions_without_rating",
]


# Dummy public symbol to satisfy package layout test
def memory_correctness_setup() -> str:
    """Dummy function to satisfy package layout convention."""
    return "memory_correctness_setup"