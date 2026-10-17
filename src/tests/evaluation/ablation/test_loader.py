"""Test cho module loader ablation."""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from package.evaluation.ablation._loader import (
    check_compatibility,
    load_config_data,
    load_group_data,
    load_scored_data,
    validate_contrast_config,
)
from package.config.load_config import ConfigError


def test_load_scored_data():
    """Load scored.jsonl phải trả list dict."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        scored_path = tmpdir / "scored.jsonl"
        
        # Write test data
        test_data = [
            {"request_id": "req1", "agent": "planner", "task_success": True},
            {"request_id": "req2", "agent": "planner", "task_success": False},
        ]
        scored_path.write_text("\n".join(json.dumps(d) for d in test_data), encoding="utf-8")
        
        result = load_scored_data(tmpdir)
        
        assert len(result) == 2
        assert result[0]["request_id"] == "req1"
        assert result[1]["request_id"] == "req2"


def test_load_scored_data_not_found():
    """Load scored.jsonl từ thư mục không có file phải ném ConfigError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        with pytest.raises(ConfigError, match="scored.jsonl not found"):
            load_scored_data(tmpdir)


def test_load_config_data():
    """Load config.yaml phải trả dict."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        config_path = tmpdir / "config.yaml"
        
        test_config = {
            "config": {"seed": 42, "k": 10},
            "dataset": {"eval_on": "validation"},
        }
        config_path.write_text(yaml.dump(test_config), encoding="utf-8")
        
        result = load_config_data(tmpdir)
        
        assert result["config"]["seed"] == 42
        assert result["config"]["k"] == 10


def test_load_config_data_not_found():
    """Load config.yaml từ thư mục không có file phải ném ConfigError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        with pytest.raises(ConfigError, match="config.yaml not found"):
            load_config_data(tmpdir)


def test_check_compatibility_match():
    """Hai config tương thích phải trả (True, '')."""
    config_a = {
        "config": {"seed": 42, "per_segment": 20, "language": "vi", "k": 10},
        "dataset": {"eval_on": "validation"},
    }
    config_b = {
        "config": {"seed": 42, "per_segment": 20, "language": "vi", "k": 10},
        "dataset": {"eval_on": "validation"},
    }
    
    compatible, reason = check_compatibility(config_a, config_b)
    
    assert compatible is True
    assert reason == ""


def test_check_compatibility_seed_mismatch():
    """Hai config với seed khác nhau phải trả (False, reason)."""
    config_a = {
        "config": {"seed": 42, "per_segment": 20, "language": "vi", "k": 10},
        "dataset": {"eval_on": "validation"},
    }
    config_b = {
        "config": {"seed": 43, "per_segment": 20, "language": "vi", "k": 10},
        "dataset": {"eval_on": "validation"},
    }
    
    compatible, reason = check_compatibility(config_a, config_b)
    
    assert compatible is False
    assert "seed mismatch" in reason


def test_check_compatibility_per_segment_mismatch():
    """Hai config với per_segment khác nhau phải trả (False, reason)."""
    config_a = {
        "config": {"seed": 42, "per_segment": 20, "language": "vi", "k": 10},
        "dataset": {"eval_on": "validation"},
    }
    config_b = {
        "config": {"seed": 42, "per_segment": 10, "language": "vi", "k": 10},
        "dataset": {"eval_on": "validation"},
    }
    
    compatible, reason = check_compatibility(config_a, config_b)
    
    assert compatible is False
    assert "per_segment mismatch" in reason


def test_check_compatibility_eval_on_mismatch():
    """Hai config với eval_on khác nhau phải trả (False, reason)."""
    config_a = {
        "config": {"seed": 42, "per_segment": 20, "language": "vi", "k": 10},
        "dataset": {"eval_on": "validation"},
    }
    config_b = {
        "config": {"seed": 42, "per_segment": 20, "language": "vi", "k": 10},
        "dataset": {"eval_on": "test"},
    }
    
    compatible, reason = check_compatibility(config_a, config_b)
    
    assert compatible is False
    assert "eval_on mismatch" in reason


def test_validate_contrast_config_valid():
    """Validate contrast hợp lệ phải không ném lỗi."""
    contrast = {
        "name": "test_contrast",
        "a": ["planner", "config_a"],
        "b": ["planner", "config_b"],
    }
    groups = {"config_a": ["exp_001"], "config_b": ["exp_002"]}
    
    # Không nên ném lỗi
    validate_contrast_config(contrast, groups)


def test_validate_contrast_config_missing_name():
    """Contrast thiếu name phải ném ConfigError."""
    contrast = {
        "a": ["planner", "config_a"],
        "b": ["planner", "config_b"],
    }
    groups = {"config_a": ["exp_001"], "config_b": ["exp_002"]}
    
    with pytest.raises(ConfigError, match="must have 'name'"):
        validate_contrast_config(contrast, groups)


def test_validate_contrast_config_missing_a():
    """Contrast thiếu a phải ném ConfigError."""
    contrast = {
        "name": "test",
        "b": ["planner", "config_b"],
    }
    groups = {"config_a": ["exp_001"], "config_b": ["exp_002"]}
    
    with pytest.raises(ConfigError, match="must have 'a' and 'b'"):
        validate_contrast_config(contrast, groups)


def test_validate_contrast_config_group_not_found():
    """Contrast tham chiếu group không tồn tại phải ném ConfigError."""
    contrast = {
        "name": "test",
        "a": ["planner", "config_c"],
        "b": ["planner", "config_b"],
    }
    groups = {"config_a": ["exp_001"], "config_b": ["exp_002"]}
    
    with pytest.raises(ConfigError, match="Group 'config_c' not found"):
        validate_contrast_config(contrast, groups)
