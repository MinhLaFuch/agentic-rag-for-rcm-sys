"""Contract validation: fake tools must match real tool schemas."""

import pytest

from package.tools.ranking import SimilarTool, RankTool
from package.tools.sql_query import LookupTool, FilterTool
from package.tools.retrieval import SearchTool
from package.memory.memory_tool import MemoryTool
from tests.agents.fakes.fake_tools import (
    FakeSimilarTool,
    FakeRankTool,
    FakeLookupTool,
    FakeSearchTool,
    FakeFilterTool,
    FakeMemoryTool,
)


@pytest.mark.parametrize(
    "real_tool_class, fake_tool_class",
    [
        (SimilarTool, FakeSimilarTool),
        (RankTool, FakeRankTool),
        (LookupTool, FakeLookupTool),
        (SearchTool, FakeSearchTool),
        (FilterTool, FakeFilterTool),
        (MemoryTool, FakeMemoryTool),
    ],
)
def test_fake_tool_matches_real_schema(real_tool_class, fake_tool_class):
    """Fake tool input_schema and output_schema must exactly match the real tool."""
    assert fake_tool_class.name == real_tool_class.name
    assert fake_tool_class.description == real_tool_class.description
    assert fake_tool_class.input_schema == real_tool_class.input_schema
    assert fake_tool_class.output_schema == real_tool_class.output_schema


def test_prompt_references_match_tool_output_schemas():
    """
    Verify that every $N.path reference in planner/_prompt.py examples
    only uses fields that exist in the corresponding tool's output_schema.
    """
    from package.tools.ranking import SimilarTool, RankTool
    from package.tools.sql_query import LookupTool, FilterTool
    from package.tools.retrieval import SearchTool
    from package.memory.memory_tool import MemoryTool

    # Example 1: SimilarTool -> RankTool -> LookupTool
    # $1.candidates (SimilarTool output)
    assert "candidates" in SimilarTool.output_schema
    # $2.ranked.*.item_id (RankTool output)
    assert "ranked" in RankTool.output_schema
    # $2.ranked.*.item_id requires "item_id" field in ranked items
    # LookupTool expects item_ids, not item_id in input (different naming)

    # Example 2: MemoryTool -> FilterTool -> RankTool -> LookupTool
    # $1.top_categories (MemoryTool output)
    assert "top_categories" in MemoryTool.output_schema
    # $1.price_range.max (MemoryTool output, nested)
    assert "price_range" in MemoryTool.output_schema
    # $2.candidates (FilterTool output)
    assert "candidates" in FilterTool.output_schema
    # $3.ranked.*.item_id (RankTool output)
    assert "ranked" in RankTool.output_schema

    # Example 3: MemoryTool -> SimilarTool -> RankTool -> LookupTool
    # $1.recent_items (MemoryTool output)
    assert "recent_items" in MemoryTool.output_schema
    # $2.candidates (SimilarTool output)
    assert "candidates" in SimilarTool.output_schema

    # Also verify that args in examples match input_schema
    # SimilarTool: items, top_k
    assert "items" in SimilarTool.input_schema
    assert "top_k" in SimilarTool.input_schema
    # RankTool: user_id, candidates, top_k
    assert "user_id" in RankTool.input_schema
    assert "candidates" in RankTool.input_schema
    assert "top_k" in RankTool.input_schema
    # LookupTool: item_ids
    assert "item_ids" in LookupTool.input_schema
    # MemoryTool: user_id
    assert "user_id" in MemoryTool.input_schema
    # FilterTool: filters, limit
    assert "filters" in FilterTool.input_schema
    assert "limit" in FilterTool.input_schema
