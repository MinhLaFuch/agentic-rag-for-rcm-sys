"""Smoke tests for the data_pipeline CLI wrappers.

The stage logic lives in ``package.data.pipeline`` / ``package.data.manifest``
(unit-tested); these tests cover the thin ``main()`` orchestration that no other
test imports — arg parsing, stage ordering, pre-checks, and verify_tag output.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from scripts.data_pipeline import run_pipeline, verify_tag


def _fake_paths(tmp_path: Path, domains=("DomainA",)):
    """Minimal DataPaths stand-in covering the attrs the CLIs touch."""
    cleaned_dir = tmp_path / "cleaned"
    cleaned_dir.mkdir()
    cleaned_file = cleaned_dir / "DomainA" / "interactions.parquet"
    cleaned_file.parent.mkdir(parents=True)
    cleaned_file.write_bytes(b"x")
    return SimpleNamespace(
        cleaned_path=lambda domain: cleaned_dir / domain / "interactions.parquet",
        cleaned_dir=cleaned_dir,
        filtered_path=tmp_path / "filtered" / "interactions.parquet",
        splits_dir=tmp_path / "splits",
        mapped_dir=tmp_path / "mapped",
        corpus_dir=tmp_path / "corpus",
        corpus_path=tmp_path / "corpus" / "corpus.pkl",
        review_path=lambda domain: tmp_path / "raw" / f"{domain}.parquet",
        split_path=lambda name: tmp_path / "splits" / f"{name}.parquet",
        item_knn_path=lambda split: tmp_path / "knn" / f"item_knn_{split}.npz",
        stage1_manifest_path=lambda domain: tmp_path / "manifests" / f"stage_1_{domain}.json",
        tag="test_tag",
    )


def _patch_common(monkeypatch, paths, domains=("DomainA",)):
    monkeypatch.setattr(run_pipeline, "get_domains", lambda: list(domains))
    monkeypatch.setattr(run_pipeline, "get_data_paths", lambda domains=None, **kw: paths)
    monkeypatch.setattr(run_pipeline, "load_config", lambda key: {
        "split": {"item_knn_splits": ["validation"], "data_protocol": "legacy_kcore_before_split"}
    })
    calls = []
    for name in ("clean_domain", "merge_filter_domains", "map_split", "build_artifacts"):
        monkeypatch.setattr(run_pipeline, name, lambda *a, _n=name, **k: calls.append(_n))
    return calls


def test_run_pipeline_runs_stages_in_fixed_order(monkeypatch, tmp_path):
    paths = _fake_paths(tmp_path)
    calls = _patch_common(monkeypatch, paths)
    monkeypatch.setattr(sys, "argv", ["run_pipeline.py", "--stages", "3,2", "--domain", "DomainA"])
    run_pipeline.main()
    assert calls == ["merge_filter_domains", "map_split"]


def test_run_pipeline_stage4_receives_protocol_and_eval_splits(monkeypatch, tmp_path):
    paths = _fake_paths(tmp_path)
    seen = {}
    _patch_common(monkeypatch, paths)
    monkeypatch.setattr(run_pipeline, "build_artifacts",
                        lambda *a, **k: seen.update(k))
    monkeypatch.setattr(sys, "argv",
                        ["run_pipeline.py", "--stages", "4", "--domain", "DomainA",
                         "--skip-corpus", "--skip-item-knn"])
    # stage 4 pre-check requires mapped_dir to exist when stage 3 not selected
    paths.mapped_dir.mkdir(parents=True, exist_ok=True)
    run_pipeline.main()
    assert seen["eval_on"] == ["validation"] and seen["skip_corpus"] and seen["skip_item_knn"]


def test_run_pipeline_precheck_fails_closed_on_missing_input(monkeypatch, tmp_path, capsys):
    paths = _fake_paths(tmp_path)
    paths.cleaned_path = lambda domain: tmp_path / "absent" / "interactions.parquet"
    _patch_common(monkeypatch, paths)
    monkeypatch.setattr(sys, "argv", ["run_pipeline.py", "--stages", "2", "--domain", "DomainA"])
    with pytest.raises(SystemExit) as exc:
        run_pipeline.main()
    assert exc.value.code == 1
    assert "Stage 2 input missing" in capsys.readouterr().err


def test_parse_stages_rejects_garbage():
    import argparse
    with pytest.raises(argparse.ArgumentTypeError):
        run_pipeline._parse_stages("two")
    assert run_pipeline._parse_stages("4,1,4") == [1, 4]


def _patch_verify_tag(monkeypatch, tmp_path, manifest_result=None, manifest_exc=None):
    paths = _fake_paths(tmp_path)
    monkeypatch.setattr(verify_tag, "get_domains", lambda: ["DomainA"])
    monkeypatch.setattr(verify_tag, "get_data_paths", lambda domains=None: paths)
    fake = MagicMock()
    if manifest_exc is not None:
        fake.side_effect = manifest_exc
    else:
        fake.return_value = manifest_result or {"status": "ok", "manifest_sha256": "abc", "warnings": []}
    monkeypatch.setattr(verify_tag, "verify_tag_manifest", fake)
    return paths


def test_verify_tag_prints_status_and_missing_rows(monkeypatch, tmp_path, capsys):
    _patch_verify_tag(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "argv", ["verify_tag.py", "--domain", "DomainA"])
    verify_tag.main()
    out = capsys.readouterr().out
    assert "status=ok" in out and "manifest_sha256=abc" in out and "MISSING" in out


def test_verify_tag_legacy_unmanifested_warns_and_returns(monkeypatch, tmp_path, capsys):
    _patch_verify_tag(monkeypatch, tmp_path,
                      manifest_result={"status": "legacy_unmanifested",
                                       "manifest_sha256": "none", "warnings": []})
    monkeypatch.setattr(sys, "argv", ["verify_tag.py"])
    verify_tag.main()
    assert "legacy_unmanifested" in capsys.readouterr().out


def test_verify_tag_mismatch_exits_nonzero(monkeypatch, tmp_path, capsys):
    _patch_verify_tag(monkeypatch, tmp_path, manifest_exc=ValueError("chain broken"))
    monkeypatch.setattr(sys, "argv", ["verify_tag.py"])
    with pytest.raises(SystemExit) as exc:
        verify_tag.main()
    assert exc.value.code == 1
    assert "status=MISMATCH" in capsys.readouterr().out
