"""Build (VectorStore, TextEncoder) từ artifacts của build_semantic_embeddings.py.

Artifacts dir phải chứa output hoàn chỉnh của lệnh ``build`` (manifest.json,
documents.jsonl, item_ids.json, vectors.npy, valid.npy). Mọi checksum trong
manifest được verify trước khi load — artifact bị sửa/thiếu sẽ raise thay vì
lặng lẽ trả về vector sai.

Encoder mặc định lazy-import sentence-transformers và load snapshot đã pin
trong encoder lock (từ lệnh ``pin``). Runtime env không có torch/
sentence-transformers → gọi hàm này với ``enabled=true`` sẽ raise rõ ràng;
truyền ``encoder_factory`` để inject encoder khác (tests, env riêng).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from .text_encoder import TextEncoder
from .vector_store import VectorStore

_REQUIRED_ARTIFACTS = ("documents.jsonl", "item_ids.json", "vectors.npy", "valid.npy")


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _verify_semantic_artifacts(artifacts_dir: Path) -> tuple[dict[str, Any], list[str], np.ndarray, np.ndarray]:
    manifest_path = artifacts_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"dense retrieval manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "complete":
        raise ValueError(f"semantic artifacts not complete (status={manifest.get('status')!r}): {artifacts_dir}")
    hashes = manifest.get("artifact_hashes") or {}
    for name in _REQUIRED_ARTIFACTS:
        path = artifacts_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"semantic artifact missing: {path}")
        expected = hashes.get(name)
        if expected is None or _sha256(path) != expected:
            raise ValueError(f"semantic artifact checksum mismatch: {name}")

    item_ids = json.loads((artifacts_dir / "item_ids.json").read_text(encoding="utf-8"))
    vectors = np.load(artifacts_dir / "vectors.npy")
    valid = np.load(artifacts_dir / "valid.npy")
    dimensions = int((manifest.get("identity") or {}).get("dimensions", 0))
    if not item_ids or len(item_ids) != len(vectors) or vectors.shape != (len(item_ids), dimensions):
        raise ValueError(f"semantic artifact shape mismatch: items={len(item_ids)} vectors={vectors.shape} dim={dimensions}")
    if vectors.dtype != np.float32 or valid.dtype != np.bool_ or valid.shape != (len(item_ids),):
        raise ValueError("semantic artifact dtype mismatch (expected float32 vectors, bool valid mask)")
    if int(valid.sum()) != int(manifest.get("valid_rows", -1)):
        raise ValueError("valid.npy count does not match manifest valid_rows")
    if len(set(item_ids)) != len(item_ids):
        raise ValueError("duplicate item_id in semantic artifacts")
    return manifest, item_ids, vectors, valid


def _verify_encoder_lock(lock_path: Path) -> dict[str, Any]:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("status") != "ready":
        raise ValueError(f"encoder lock not ready (status={lock.get('status')!r}): {lock_path}")
    snapshot = Path(lock.get("snapshot") or "")
    if not snapshot.is_dir():
        raise FileNotFoundError(f"encoder snapshot missing: {snapshot}")
    for name, expected in (lock.get("model_files") or {}).items():
        path = snapshot / name
        if not path.is_file() or _sha256(path) != expected:
            raise ValueError(f"encoder model file checksum mismatch: {name}")
    return lock


def _default_encoder_factory(lock: dict[str, Any]) -> Callable[[Sequence[str]], object]:
    try:
        import torch
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "dense retrieval enabled but sentence-transformers/torch is not installed "
            "in this environment. Install them or set dense_retrieval.enabled=false."
        ) from exc
    torch.manual_seed(42)
    model = SentenceTransformer(lock["snapshot"], local_files_only=True, trust_remote_code=False, device="cpu")
    model.eval()

    def encode(texts: Sequence[str]):
        return model.encode(
            list(texts), batch_size=64, normalize_embeddings=True,
            convert_to_numpy=True, show_progress_bar=False,
        )

    return encode


def build_dense_retrieval(
    artifacts_dir: str | Path,
    encoder_lock: str | Path | None,
    *,
    rrf_k: int = 60,
    encoder_factory: Callable[[dict[str, Any]], Callable[[Sequence[str]], object]] | None = None,
) -> tuple[VectorStore, TextEncoder, dict[str, Any]]:
    """Load verified semantic artifacts + encoder → (VectorStore, TextEncoder, provenance).

    encoder_factory(lock_dict) -> encode_fn(texts) -> 2-D array; injectable for tests.
    """
    artifacts_path = Path(artifacts_dir)
    manifest, item_ids, vectors, valid = _verify_semantic_artifacts(artifacts_path)
    keep_ids = [item_ids[i] for i in range(len(item_ids)) if valid[i]]
    if bool(valid.all()) and vectors.dtype == np.float32:
        store = VectorStore(keep_ids, vectors)
    else:
        store = VectorStore(keep_ids, np.asarray(vectors[valid], dtype=np.float32))

    if encoder_factory is None:
        if encoder_lock is None:
            raise ValueError("dense retrieval requires encoder_lock (or encoder_factory) for query encoding")
        lock = _verify_encoder_lock(Path(encoder_lock))
        encode_fn = _default_encoder_factory(lock)
    else:
        lock = _verify_encoder_lock(Path(encoder_lock)) if encoder_lock is not None else {}
        encode_fn = encoder_factory(lock)

    encoder = TextEncoder(encode_fn, dimension=int(store.dimension))
    provenance = {
        "artifacts_dir": str(artifacts_path),
        "manifest_sha256": _sha256(artifacts_path / "manifest.json"),
        "rows": int(manifest.get("rows", len(item_ids))),
        "valid_rows": int(valid.sum()),
        "encoder_model_id": (manifest.get("identity") or {}).get("model_id"),
        "encoder_revision": (lock or {}).get("revision"),
        "rrf_k": int(rrf_k),
    }
    return store, encoder, provenance
