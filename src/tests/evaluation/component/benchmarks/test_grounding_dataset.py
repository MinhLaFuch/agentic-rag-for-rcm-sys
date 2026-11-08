"""Dataset lint tests for the grounding benchmark.

The benchmark can only be as good as its labels: these tests fail loudly when
the committed dataset drifts into states the benchmark cannot measure.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from package.evaluation.component._loader import load_cases
from package.evaluation.component.benchmarks.grounding_benchmark import EXPECTED_METRIC_KEYS

DATASET = Path(__file__).parents[4] / "package" / "evaluation" / "component" / "benchmarks" / "grounding_dataset.jsonl"

# Request markers that make a "prompt-injection" tag honest. A case tagged
# prompt-injection whose request contains none of these is mislabeled
# (grounding_030 was exactly that: a legit translation request).
INJECTION_MARKERS = re.compile(
    r"ignore|instruction|system\s*:|override|forget|prompt|bypass|disregard|jailbreak|admin|reveal|previous",
    re.IGNORECASE,
)


@pytest.fixture(scope="module")
def cases():
    return load_cases(DATASET)


def test_dataset_nonempty(cases):
    assert len(cases) >= 30


def test_every_case_has_evidence(cases):
    """run_component raises on empty evidence -> such a case can never pass."""
    empty = [c.case_id for c in cases if not c.input.get("evidence")]
    assert empty == [], f"cases with empty evidence always fail: {empty}"


def test_prompt_injection_tag_requires_injection_markers(cases):
    bad = [
        c.case_id
        for c in cases
        if "prompt-injection" in c.tags
        and not INJECTION_MARKERS.search(c.input.get("user_request", ""))
    ]
    assert bad == [], f"prompt-injection tag but request has no injection markers: {bad}"


def test_expected_keys_are_assertable(cases):
    """expected may only contain keys score_component actually compares."""
    bad = []
    for c in cases:
        unknown = set(c.expected) - set(EXPECTED_METRIC_KEYS)
        if unknown:
            bad.append((c.case_id, sorted(unknown)))
    assert bad == [], f"expected keys that label_agreement ignores: {bad}"


def test_expected_values_in_range(cases):
    for c in cases:
        e = c.expected
        for key in ("grounding_rate", "hallucination_rate"):
            if key in e:
                assert 0.0 <= e[key] <= 1.0, (c.case_id, key, e[key])
        if "claims_supported" in e:
            assert e["claims_supported"] >= 0


def test_case_ids_unique(cases):
    ids = [c.case_id for c in cases]
    assert len(ids) == len(set(ids))


def test_dataset_is_valid_jsonl():
    for i, line in enumerate(DATASET.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            json.loads(line)  # raises on malformed line
