"""Contract validation: fake tools must match real tool schemas."""

import pytest

from package.tools.ranking import ItemCFTool, RecoModelTool
from package.tools.sql_query import QueryTool, SQLTool
from package.tools.retrieval import SemanticSearchTool
from package.memory.memory_tool import MemoryTool
from tests.agents.fakes.fake_tools import (
    FakeItemCFTool,
    FakeRecoModelTool,
    FakeQueryTool,
    FakeSemanticSearchTool,
    FakeSQLTool,
    FakeMemoryTool,
)


@pytest.mark.parametrize(
    "real_tool_class, fake_tool_class",
    [
        (ItemCFTool, FakeItemCFTool),
        (RecoModelTool, FakeRecoModelTool),
        (QueryTool, FakeQueryTool),
        (SemanticSearchTool, FakeSemanticSearchTool),
        (SQLTool, FakeSQLTool),
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
    from package.tools.ranking import ItemCFTool, RecoModelTool
    from package.tools.sql_query import QueryTool, SQLTool
    from package.tools.retrieval import SemanticSearchTool
    from package.memory.memory_tool import MemoryTool

    # Example 1: ItemCFTool -> RecoModelTool -> QueryTool
    # $1.candidates (ItemCFTool output)
    assert "candidates" in ItemCFTool.output_schema
    # $2.ranked.*.item_id (RecoModelTool output)
    assert "ranked" in RecoModelTool.output_schema
    # $2.ranked.*.item_id requires "item_id" field in ranked items
    # QueryTool expects item_ids, not item_id in input (different naming)

    # Example 2: MemoryTool -> SQLTool -> RecoModelTool -> QueryTool
    # $1.top_categories (MemoryTool output)
    assert "top_categories" in MemoryTool.output_schema
    # $1.price_range.max (MemoryTool output, nested)
    assert "price_range" in MemoryTool.output_schema
    # $2.candidates (SQLTool output)
    assert "candidates" in SQLTool.output_schema
    # $3.ranked.*.item_id (RecoModelTool output)
    assert "ranked" in RecoModelTool.output_schema

    # Example 3: MemoryTool -> ItemCFTool -> RecoModelTool -> QueryTool
    # $1.recent_items (MemoryTool output)
    assert "recent_items" in MemoryTool.output_schema
    # $2.candidates (ItemCFTool output)
    assert "candidates" in ItemCFTool.output_schema

    # Also verify that args in examples match input_schema
    # ItemCFTool: items, top_k
    assert "items" in ItemCFTool.input_schema
    assert "top_k" in ItemCFTool.input_schema
    # RecoModelTool: user_id, candidates, top_k
    assert "user_id" in RecoModelTool.input_schema
    assert "candidates" in RecoModelTool.input_schema
    assert "top_k" in RecoModelTool.input_schema
    # QueryTool: item_ids
    assert "item_ids" in QueryTool.input_schema
    # MemoryTool: user_id
    assert "user_id" in MemoryTool.input_schema
    # SQLTool: filters, limit
    assert "filters" in SQLTool.input_schema
    assert "limit" in SQLTool.input_schema
