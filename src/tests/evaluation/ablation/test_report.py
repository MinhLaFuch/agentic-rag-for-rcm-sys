"""Test cho module report ablation."""

import tempfile
from pathlib import Path

import pytest

from package.evaluation.ablation._limits import AblationLimits
from package.evaluation.ablation._report import (
    render_markdown_report,
    write_csv,
    write_disagreements,
    write_json,
)


def test_render_markdown_report_basic():
    """Render markdown report phải sinh ra chuỗi hợp lệ."""
    results = {
        "all_kinds": {
            "similar": {
                "task_success": {
                    "mean_a": 0.8,
                    "mean_b": 0.9,
                    "diff": 0.1,
                    "ci_lower": 0.05,
                    "ci_upper": 0.15,
                    "n": 100,
                }
            }
        },
        "n_pairs": 100,
        "variance": {"note": "Only 1 run per group"},
    }
    
    limits = AblationLimits(
        bootstrap_resamples=10000,
        confidence=0.95,
        min_n_warn=20,
        seed=42,
        metrics=["task_success"],
        groups={},
        contrasts=[],
        output_subdir="test",
    )
    
    report = render_markdown_report(
        results,
        "test_contrast",
        "planner",
        "planner_memory",
        "config_a",
        "config_b",
        limits,
        k=10,
        missing_columns=[],
    )
    
    assert "# Ablation Comparison" in report
    assert "test_contrast" in report
    assert "Number of paired requests:" in report
    assert "100" in report
    assert "task_success" in report
    assert "0.8000" in report  # mean_a
    assert "0.9000" in report  # mean_b
    assert "+0.1000" in report  # diff


def test_render_markdown_report_with_warning():
    """Report với n nhỏ phải in cảnh báo."""
    results = {
        "all_kinds": {},
        "n_pairs": 10,
        "variance": {"note": "Only 1 run per group"},
    }
    
    limits = AblationLimits(
        bootstrap_resamples=10000,
        confidence=0.95,
        min_n_warn=20,
        seed=42,
        metrics=["task_success"],
        groups={},
        contrasts=[],
        output_subdir="test",
    )
    
    report = render_markdown_report(
        results,
        "test_contrast",
        "planner",
        "planner_memory",
        "config_a",
        "config_b",
        limits,
        k=10,
        missing_columns=[],
    )
    
    assert "WARNING" in report
    assert "n = 10 < 20" in report


def test_render_markdown_report_with_error():
    """Report với error phải hiển thị error."""
    results = {"error": "seed mismatch: 42 vs 43"}
    
    limits = AblationLimits(
        bootstrap_resamples=10000,
        confidence=0.95,
        min_n_warn=20,
        seed=42,
        metrics=["task_success"],
        groups={},
        contrasts=[],
        output_subdir="test",
    )
    
    report = render_markdown_report(
        results,
        "test_contrast",
        "planner",
        "planner_memory",
        "config_a",
        "config_b",
        limits,
        k=10,
        missing_columns=[],
    )
    
    assert "ERROR" in report
    assert "seed mismatch" in report


def test_write_csv():
    """Write CSV phải tạo file hợp lệ."""
    results = {
        "all_kinds": {
            "similar": {
                "task_success": {
                    "mean_a": 0.8,
                    "mean_b": 0.9,
                    "diff": 0.1,
                    "ci_lower": 0.05,
                    "ci_upper": 0.15,
                    "n": 100,
                }
            }
        },
        "n_pairs": 100,
        "variance": {"note": "Only 1 run per group"},
    }
    
    limits = AblationLimits(
        bootstrap_resamples=10000,
        confidence=0.95,
        min_n_warn=20,
        seed=42,
        metrics=["task_success"],
        groups={},
        contrasts=[],
        output_subdir="test",
    )
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        csv_path = tmpdir / "test.csv"
        
        write_csv(
            results,
            "test_contrast",
            "planner",
            "planner_memory",
            "config_a",
            "config_b",
            limits,
            k=10,
            output_path=csv_path,
        )
        
        assert csv_path.exists()
        content = csv_path.read_text(encoding="utf-8")
        assert "contrast" in content
        assert "agent_a" in content
        assert "task_success" in content


def test_write_json():
    """Write JSON phải tạo file hợp lệ."""
    results = {
        "all_kinds": {},
        "n_pairs": 100,
        "variance": {"note": "Only 1 run per group"},
    }
    
    limits = AblationLimits(
        bootstrap_resamples=10000,
        confidence=0.95,
        min_n_warn=20,
        seed=42,
        metrics=["task_success"],
        groups={},
        contrasts=[],
        output_subdir="test",
    )
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        json_path = tmpdir / "test.json"
        
        write_json(
            results,
            "test_contrast",
            "planner",
            "planner_memory",
            "config_a",
            "config_b",
            limits,
            k=10,
            output_path=json_path,
        )
        
        assert json_path.exists()
        import json
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["contrast"] == "test_contrast"
        assert data["agent_a"] == "planner"


def test_write_disagreements():
    """Write disagreements.jsonl phải tạo file hợp lệ."""
    disagreements = [
        {
            "request_id": "req1",
            "text": "test",
            "kind": "similar",
            "segment": "sparse",
            "a_trajectory": {"plan": [], "steps": [], "reflections": 0},
            "b_trajectory": {"plan": [], "steps": [], "reflections": 0},
        }
    ]
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        jsonl_path = tmpdir / "disagreements.jsonl"
        
        write_disagreements(disagreements, jsonl_path)
        
        assert jsonl_path.exists()
        content = jsonl_path.read_text(encoding="utf-8")
        assert "req1" in content
        assert len(content.strip().split("\n")) == 1
