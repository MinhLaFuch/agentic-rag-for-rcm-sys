"""Create synthetic corpus for correctness testing."""

from __future__ import annotations

from package.tools.corpus import ItemCorpus
from .create_test_meta import create_test_meta


def create_test_corpus() -> ItemCorpus:
    """Create synthetic corpus for correctness testing."""
    return ItemCorpus.from_dataframe(create_test_meta())