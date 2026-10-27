"""Tests for component benchmark dataset loader."""

from __future__ import annotations

import json
import pytest
from pathlib import Path

from package.evaluation.component._loader import load_cases, save_cases, filter_cases_by_tag, filter_cases_by_metadata
from package.evaluation.component._schema import BenchmarkCase


@pytest.fixture(autouse=True)
def ignore_deprecation_warnings():
    """Ignore datetime.utcnow deprecation warnings in tests."""
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning, message="datetime.datetime.utcnow")


def test_load_cases_from_json(tmp_path):
    """Test loading cases from JSON file."""
    data = [
        {
            "case_id": "test_001",
            "input": {"user_id": "u1"},
            "expected": {"known": True},
            "tags": ["normal"],
            "metadata": {"description": "Test case"},
        }
    ]
    json_path = tmp_path / "test.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    cases = load_cases(json_path)
    assert len(cases) == 1
    assert cases[0].case_id == "test_001"
    assert cases[0].input == {"user_id": "u1"}
    assert cases[0].expected == {"known": True}
    assert cases[0].tags == ["normal"]
    assert cases[0].metadata == {"description": "Test case"}


def test_load_cases_from_json_with_cases_key(tmp_path):
    """Test loading cases from JSON file with 'cases' key."""
    data = {
        "cases": [
            {
                "case_id": "test_001",
                "input": {"user_id": "u1"},
                "expected": {"known": True},
                "tags": ["normal"],
            }
        ]
    }
    json_path = tmp_path / "test.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    cases = load_cases(json_path)
    assert len(cases) == 1
    assert cases[0].case_id == "test_001"


def test_load_cases_from_jsonl(tmp_path):
    """Test loading cases from JSONL file."""
    jsonl_path = tmp_path / "test.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"case_id": "test_001", "input": {"user_id": "u1"}, "expected": {"known": True}, "tags": ["normal"]}) + "\n")
        f.write(json.dumps({"case_id": "test_002", "input": {"user_id": "u2"}, "expected": {"known": False}, "tags": ["negative"]}) + "\n")

    cases = load_cases(jsonl_path)
    assert len(cases) == 2
    assert cases[0].case_id == "test_001"
    assert cases[1].case_id == "test_002"


def test_load_cases_file_not_found():
    """Test that FileNotFoundError is raised for missing file."""
    with pytest.raises(FileNotFoundError):
        load_cases("nonexistent.json")


def test_load_cases_invalid_format(tmp_path):
    """Test that ValueError is raised for invalid format."""
    invalid_path = tmp_path / "test.txt"
    invalid_path.write_text("not json")

    with pytest.raises(ValueError, match="Unsupported file format"):
        load_cases(invalid_path)


def test_save_cases_json(tmp_path):
    """Test saving cases to JSON file."""
    cases = [
        BenchmarkCase(
            case_id="test_001",
            input={"user_id": "u1"},
            expected={"known": True},
            tags=["normal"],
        )
    ]
    output_path = tmp_path / "output.json"
    save_cases(cases, output_path, format="json")

    with open(output_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 1
    assert data[0]["case_id"] == "test_001"


def test_save_cases_jsonl(tmp_path):
    """Test saving cases to JSONL file."""
    cases = [
        BenchmarkCase(
            case_id="test_001",
            input={"user_id": "u1"},
            expected={"known": True},
            tags=["normal"],
        )
    ]
    output_path = tmp_path / "output.jsonl"
    save_cases(cases, output_path, format="jsonl")

    with open(output_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["case_id"] == "test_001"


def test_save_cases_invalid_format(tmp_path):
    """Test that ValueError is raised for invalid format."""
    cases = [BenchmarkCase(case_id="test", input={}, expected={})]
    output_path = tmp_path / "output.txt"

    with pytest.raises(ValueError, match="Unsupported format"):
        save_cases(cases, output_path, format="txt")


def test_filter_cases_by_tag():
    """Test filtering cases by tags (OR logic)."""
    cases = [
        BenchmarkCase(case_id="c1", input={}, expected={}, tags=["normal"]),
        BenchmarkCase(case_id="c2", input={}, expected={}, tags=["negative"]),
        BenchmarkCase(case_id="c3", input={}, expected={}, tags=["normal", "hard"]),
    ]

    # Filter by single tag
    filtered = filter_cases_by_tag(cases, ["normal"])
    assert len(filtered) == 2
    assert {c.case_id for c in filtered} == {"c1", "c3"}

    # Filter by multiple tags (OR logic)
    filtered = filter_cases_by_tag(cases, ["normal", "negative"])
    assert len(filtered) == 3

    # No filter
    filtered = filter_cases_by_tag(cases, None)
    assert len(filtered) == 3


def test_filter_cases_by_metadata():
    """Test filtering cases by metadata (AND logic)."""
    cases = [
        BenchmarkCase(case_id="c1", input={}, expected={}, metadata={"difficulty": "easy", "category": "memory"}),
        BenchmarkCase(case_id="c2", input={}, expected={}, metadata={"difficulty": "hard", "category": "memory"}),
        BenchmarkCase(case_id="c3", input={}, expected={}, metadata={"difficulty": "easy", "category": "planner"}),
    ]

    # Filter by single key
    filtered = filter_cases_by_metadata(cases, {"difficulty": "easy"})
    assert len(filtered) == 2
    assert {c.case_id for c in filtered} == {"c1", "c3"}

    # Filter by multiple keys (AND logic)
    filtered = filter_cases_by_metadata(cases, {"difficulty": "easy", "category": "memory"})
    assert len(filtered) == 1
    assert filtered[0].case_id == "c1"

    # No filter
    filtered = filter_cases_by_metadata(cases, {})
    assert len(filtered) == 3
