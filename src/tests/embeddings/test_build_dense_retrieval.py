"""Tests for build_dense_retrieval: verified artifact loading + encoder injection."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from package.embeddings import VectorStore
from package.embeddings.build_dense_retrieval import build_dense_retrieval


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_artifacts(tmp_path: Path) -> Path:
    out = tmp_path / "embeddings"
    out.mkdir()
    item_ids = ["D::a", "D::b", "D::c"]
    vectors = np.asarray([[1.0, 0.0], [0.0, 1.0], [0.6, 0.8]], dtype=np.float32)
    valid = np.asarray([True, True, False], dtype=np.bool_)
    (out / "item_ids.json").write_text(json.dumps(item_ids), encoding="utf-8")
    np.save(out / "vectors.npy", vectors)
    np.save(out / "valid.npy", valid)
    (out / "documents.jsonl").write_text('{"item_id":"D::a"}\n', encoding="utf-8")
    hashes = {name: _sha256(out / name) for name in ("documents.jsonl", "item_ids.json", "vectors.npy", "valid.npy")}
    manifest = {
        "status": "complete",
        "rows": 3,
        "valid_rows": 2,
        "invalid_rows": 1,
        "artifact_hashes": hashes,
        "identity": {"dimensions": 2, "model_id": "test-model", "dtype": "float32"},
    }
    (out / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return out


def test_build_dense_retrieval_loads_only_valid_rows(tmp_path):
    artifacts = _write_artifacts(tmp_path)
    store, encoder, provenance = build_dense_retrieval(
        artifacts, None, encoder_factory=lambda lock: (lambda texts: np.tile([1.0, 0.0], (len(texts), 1)))
    )
    assert isinstance(store, VectorStore)
    assert len(store) == 2
    result = store.search(np.asarray([1.0, 0.0], dtype=np.float32), top_k=2)
    assert result[0][0] == "D::a"
    assert encoder.encode(["hello"]).shape == (1, 2)
    assert provenance["valid_rows"] == 2
    assert provenance["rows"] == 3
    assert provenance["rrf_k"] == 60


def test_build_dense_retrieval_rejects_checksum_mismatch(tmp_path):
    artifacts = _write_artifacts(tmp_path)
    (artifacts / "vectors.npy").write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="checksum mismatch"):
        build_dense_retrieval(artifacts, None, encoder_factory=lambda lock: (lambda texts: np.zeros((len(texts), 2))))


def test_build_dense_retrieval_rejects_missing_manifest(tmp_path):
    with pytest.raises(FileNotFoundError, match="manifest"):
        build_dense_retrieval(tmp_path / "nope", None, encoder_factory=lambda lock: (lambda texts: np.zeros((len(texts), 2))))


def test_build_dense_retrieval_requires_encoder_source(tmp_path):
    artifacts = _write_artifacts(tmp_path)
    with pytest.raises(ValueError, match="encoder_lock"):
        build_dense_retrieval(artifacts, None)
