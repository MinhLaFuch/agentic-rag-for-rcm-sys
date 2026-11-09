"""Phase 6.6: reproducibility metadata + output-dir creation in the
component benchmark CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from package.evaluation.component._schema import BenchmarkResult, BenchmarkSummary
from package.evaluation.component.run_benchmark_cli import (
    _build_provenance,
    _collect_evidence_kinds,
    _dataset_sha256,
    _save_result_json,
)


def test_save_result_json_creates_missing_parents(tmp_path):
    out = tmp_path / "deep" / "nested" / "dir" / "result.json"
    _save_result_json(str(out), '{"ok": true}')
    assert json.loads(out.read_text(encoding="utf-8")) == {"ok": True}


def test_dataset_sha256_changes_when_dataset_changes(tmp_path):
    ds = tmp_path / "ds.jsonl"
    ds.write_text('{"case_id": "a"}\n', encoding="utf-8")
    h1 = _dataset_sha256(str(ds))
    assert h1 and len(h1) == 64
    ds.write_text('{"case_id": "b"}\n', encoding="utf-8")
    h2 = _dataset_sha256(str(ds))
    assert h1 != h2
    # unreadable path -> None, never an exception
    assert _dataset_sha256(str(tmp_path / "missing.jsonl")) is None


def test_provenance_includes_dataset_hash(tmp_path):
    ds = tmp_path / "ds.jsonl"
    ds.write_text("x\n", encoding="utf-8")
    prov = _build_provenance("executor", {}, str(ds))
    assert prov["dataset_sha256"] == _dataset_sha256(str(ds))


def test_provenance_answer_mode_only_for_compose_components():
    assert _build_provenance("integration", {}, "d")["answer_mode"] == "template"
    assert _build_provenance("grounding", {"mode": "llm"}, "d")["answer_mode"] == "llm"
    assert "answer_mode" not in _build_provenance("executor", {}, "d")
    assert "answer_mode" not in _build_provenance("memory", {}, "d")


def _result(case_id: str, evidence_kind: str | None) -> BenchmarkResult:
    actual = {"evidence_kind": evidence_kind} if evidence_kind else None
    return BenchmarkResult(
        case_id=case_id, actual_output=actual, success=True,
        metrics={}, latency_seconds=0.0,
    )


def test_collect_evidence_kinds_dedupes_and_sorts():
    summary = BenchmarkSummary(
        component="x",
        per_case_results=[
            _result("a", "real_execution"),
            _result("b", "real_execution"),
            _result("c", "mocked"),
            _result("d", None),
        ],
    )
    assert _collect_evidence_kinds(summary) == ["mocked", "real_execution"]
    assert _collect_evidence_kinds(BenchmarkSummary(component="x")) == []
