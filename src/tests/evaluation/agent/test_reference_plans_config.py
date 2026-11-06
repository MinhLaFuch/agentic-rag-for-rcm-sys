"""
Test that reference plans are loaded from config and cache is invalidated on change.
"""

import time
from pathlib import Path

import pytest

from package.evaluation._schema import get_reference_plans, REFERENCE_PLANS, _cached_reference_plans
from package.config.load_config import _file_mtime_cache


def test_reference_plans_loaded_from_config():
    """Test that reference plans are loaded from the config file."""
    plans = get_reference_plans()
    assert "similar" in plans
    assert "personalized" in plans
    assert "constrained" in plans
    assert "cold_text" in plans
    assert "ambiguous" in plans

    # Check structure
    assert plans["similar"] == (("SimilarTool",), ("RankTool",))
    assert plans["ambiguous"] == ()


def test_reference_plans_backward_compatibility():
    """Test that REFERENCE_PLANS dict-like accessor works."""
    # Should support __getitem__
    assert REFERENCE_PLANS["similar"] == (("SimilarTool",), ("RankTool",))

    # Should support iteration
    kinds = list(REFERENCE_PLANS.keys())
    assert "similar" in kinds
    assert "personalized" in kinds

    # Should support items()
    for kind, groups in REFERENCE_PLANS.items():
        assert isinstance(kind, str)
        assert isinstance(groups, tuple)


def test_reference_plans_cache_invalidation(tmp_path):
    """
    Test that modifying reference_plans.yaml clears the cache.
    """
    # Clear cache to avoid interference
    _file_mtime_cache.clear()
    _cached_reference_plans.cache_clear()

    agent_dir = tmp_path / "configs" / "agent"
    agent_dir.mkdir(parents=True)

    # Create initial config
    (agent_dir / "reference_plans.yaml").write_text(
        "reference_plans:\n  similar:\n    - ['SimilarTool']\n    - ['RankTool']\n  personalized:\n    - ['MemoryTool']\n"
        "    - ['SearchTool', 'FilterTool']\n    - ['RankTool']\n  constrained:\n    - ['SearchTool', 'FilterTool']\n"
        "    - ['RankTool']\n  cold_text:\n    - ['SearchTool', 'FilterTool']\n    - ['RankTool']\n  ambiguous: []\n",
        encoding="utf-8",
    )

    # Load with custom config dir
    from package.config.load_config import load_config
    cfg = load_config("agent/reference_plans", config_dir=tmp_path / "configs")
    assert cfg["reference_plans"]["similar"] == [["SimilarTool"], ["RankTool"]]

    # Wait to ensure mtime changes
    time.sleep(0.01)

    # Modify config
    (agent_dir / "reference_plans.yaml").write_text(
        "reference_plans:\n  similar:\n    - ['SearchTool']\n    - ['RankTool']\n  personalized:\n    - ['MemoryTool']\n"
        "    - ['SearchTool', 'FilterTool']\n    - ['RankTool']\n  constrained:\n    - ['SearchTool', 'FilterTool']\n"
        "    - ['RankTool']\n  cold_text:\n    - ['SearchTool', 'FilterTool']\n    - ['RankTool']\n  ambiguous: []\n",
        encoding="utf-8",
    )

    # Reload should get new values
    cfg2 = load_config("agent/reference_plans", config_dir=tmp_path / "configs")
    assert cfg2["reference_plans"]["similar"] == [["SearchTool"], ["RankTool"]]


def test_reference_plans_validation(tmp_path):
    """Test that invalid reference plans are rejected."""
    # Clear cache to avoid interference
    _file_mtime_cache.clear()

    agent_dir = tmp_path / "configs" / "agent"
    agent_dir.mkdir(parents=True)

    # Invalid config (not a dict)
    (agent_dir / "reference_plans.yaml").write_text(
        "reference_plans: 'invalid'\n",
        encoding="utf-8",
    )

    from package.config.load_config import load_config, ConfigError

    with pytest.raises(ConfigError, match="Config validation failed"):
        load_config("agent/reference_plans", config_dir=tmp_path / "configs")
