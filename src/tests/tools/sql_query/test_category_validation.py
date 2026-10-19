"""Test category validation in SQLTool and SemanticSearchTool."""

import pandas as pd
import pytest

from package.tools import ItemCorpus, SQLTool, SemanticSearchTool


def test_sqltool_rejects_invalid_category():
    """SQLTool should reject categories that don't exist in the catalog."""
    meta = pd.DataFrame({
        "parent_asin": ["a", "b"],
        "title": ["x", "y"],
        "domain": ["Test", "Test"],
        "categories": [["Electronics", "Computers"], "Audio"],
    })
    corpus = ItemCorpus.from_dataframe(meta)
    tool = SQLTool(corpus)

    # Valid category should work
    result = tool(filters={"categories_any": ["Electronics"]})
    assert result.ok

    # Invalid category should fail with helpful error
    result = tool(filters={"categories_any": ["NonExistentCategory"]})
    assert not result.ok
    assert "category 'NonExistentCategory' not found" in result.error


def test_sqltool_normalizes_category_case():
    """SQLTool should normalize category case if it exists with different case."""
    meta = pd.DataFrame({
        "parent_asin": ["a", "b"],
        "title": ["x", "y"],
        "domain": ["Test", "Test"],
        "categories": [["Electronics", "Computers"], "Audio"],
    })
    corpus = ItemCorpus.from_dataframe(meta)
    tool = SQLTool(corpus)

    # Different case should be normalized
    result = tool(filters={"categories_any": ["electronics"]})
    assert result.ok
    assert result.data["applied_filters"]["categories_any"] == ["Electronics"]


def test_sqltool_suggests_similar_categories():
    """SQLTool should suggest similar categories when given invalid one."""
    meta = pd.DataFrame({
        "parent_asin": ["a", "b", "c"],
        "title": ["x", "y", "z"],
        "domain": ["Test", "Test", "Test"],
        "categories": [["Electronics", "Computers"], "Audio", "Gaming"],
    })
    corpus = ItemCorpus.from_dataframe(meta)
    tool = SQLTool(corpus)

    # Similar typo should get suggestions
    result = tool(filters={"categories_any": ["Eletronics"]})
    assert not result.ok
    assert "Did you mean" in result.error or "not found" in result.error


def test_semantic_search_tool_validates_categories():
    """SemanticSearchTool should also validate categories."""
    meta = pd.DataFrame({
        "parent_asin": ["a", "b"],
        "title": ["Mechanical Keyboard", "Wireless Mouse"],
        "domain": ["Test", "Test"],
        "categories": [["Electronics", "Computers"], "Audio"],
    })
    corpus = ItemCorpus.from_dataframe(meta)
    tool = SemanticSearchTool(corpus)

    # Valid category should work
    result = tool(query="keyboard", filters={"categories_any": ["Electronics"]})
    assert result.ok

    # Invalid category should fail
    result = tool(query="keyboard", filters={"categories_any": ["NonExistentCategory"]})
    assert not result.ok
    assert "category 'NonExistentCategory' not found" in result.error
