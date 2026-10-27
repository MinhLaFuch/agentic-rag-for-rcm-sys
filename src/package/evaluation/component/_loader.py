"""Dataset loader for component benchmark cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ._schema import BenchmarkCase


def load_cases(dataset_path: str | Path) -> list[BenchmarkCase]:
    """Load benchmark cases from a JSON or JSONL file.

    Args:
        dataset_path: Path to the dataset file (JSON or JSONL)

    Returns:
        List of BenchmarkCase objects

    Raises:
        FileNotFoundError: If the file does not exist
        ValueError: If the file format is invalid
    """
    path = Path(dataset_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    suffix = path.suffix.lower()
    cases: list[BenchmarkCase] = []

    if suffix == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                cases = [BenchmarkCase.from_dict(item) for item in data]
            elif isinstance(data, dict) and "cases" in data:
                cases = [BenchmarkCase.from_dict(item) for item in data["cases"]]
            else:
                raise ValueError(f"Invalid JSON format: expected list or dict with 'cases' key")
    elif suffix == ".jsonl":
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    cases.append(BenchmarkCase.from_dict(data))
    else:
        raise ValueError(f"Unsupported file format: {suffix}. Expected .json or .jsonl")

    return cases


def save_cases(cases: list[BenchmarkCase], output_path: str | Path, format: str = "jsonl") -> None:
    """Save benchmark cases to a file.

    Args:
        cases: List of BenchmarkCase objects
        output_path: Path to save the file
        format: Format to save ("json" or "jsonl", default "jsonl")
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if format == "json":
        with open(path, "w", encoding="utf-8") as f:
            json.dump([case.to_dict() for case in cases], f, indent=2, ensure_ascii=False)
    elif format == "jsonl":
        with open(path, "w", encoding="utf-8") as f:
            for case in cases:
                f.write(json.dumps(case.to_dict(), ensure_ascii=False) + "\n")
    else:
        raise ValueError(f"Unsupported format: {format}. Expected 'json' or 'jsonl'")


def filter_cases_by_tag(cases: list[BenchmarkCase], tags: list[str] | None) -> list[BenchmarkCase]:
    """Filter cases by tags (OR logic: return cases that have ANY of the specified tags).

    Args:
        cases: List of BenchmarkCase objects
        tags: List of tags to filter by (None = return all)

    Returns:
        Filtered list of BenchmarkCase objects
    """
    if tags is None or not tags:
        return cases

    return [case for case in cases if any(tag in case.tags for tag in tags)]


def filter_cases_by_metadata(cases: list[BenchmarkCase], metadata_filter: dict[str, Any]) -> list[BenchmarkCase]:
    """Filter cases by metadata key-value pairs (AND logic).

    Args:
        cases: List of BenchmarkCase objects
        metadata_filter: Dict of key-value pairs to match

    Returns:
        Filtered list of BenchmarkCase objects
    """
    if not metadata_filter:
        return cases

    filtered = []
    for case in cases:
        match = True
        for key, value in metadata_filter.items():
            if case.metadata.get(key) != value:
                match = False
                break
        if match:
            filtered.append(case)

    return filtered
