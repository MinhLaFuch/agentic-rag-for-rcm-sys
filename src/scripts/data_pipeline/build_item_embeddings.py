"""
Build and save dense item embeddings for catalog retrieval.

Reads items from prebuilt ItemCorpus (SQLite) and writes:
  resource/corpus/<tag>/item_embeddings_<tag>.npz

Usage:
    python src/scripts/data_pipeline/build_item_embeddings.py --domain Video_Games --provider hash
    python src/scripts/data_pipeline/build_item_embeddings.py --domain Video_Games --provider sentence_transformers --model sentence-transformers/all-MiniLM-L6-v2
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path
from importlib.metadata import version as package_version
from package.recommenders.shared import file_hash

import numpy as np

from package.config import get_data_paths
from package.config.resolve_bundle_paths import resolve_bundle_paths
from package.embeddings import VectorStore
from package.embeddings.format_catalog_text import format_catalog_text
from package.utils import ensure_utf8_stdout


class _HashEncoder:
    """Deterministic offline pseudo-encoder for testing without GPU/network."""

    def __init__(self, dim: int = 128) -> None:
        self.dimension = dim

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dimension), dtype=np.float32)
        for i, text in enumerate(texts):
            words = text.lower().split()
            vec = np.zeros(self.dimension, dtype=np.float32)
            for w in words:
                h = hashlib.sha256(w.encode("utf-8")).digest()
                bucket = int.from_bytes(h[:4], "little") % self.dimension
                sign = 1.0 if (h[4] % 2 == 0) else -1.0
                vec[bucket] += sign
            norm = np.linalg.norm(vec)
            if norm > 1e-9:
                vec /= norm
            out[i] = vec
        return out


class _SentenceTransformerEncoder:
    """Local SentenceTransformer encoder."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", batch_size: int = 64, revision: str | None = None) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Install it with: pip install sentence-transformers"
            ) from exc
        from huggingface_hub import model_info
        self.revision = revision if revision and re.fullmatch(r"[0-9a-f]{40}", revision) else model_info(model_name, revision=revision).sha
        self.model_name = model_name
        self.model = SentenceTransformer(model_name, revision=self.revision)
        self.batch_size = batch_size
        self.dimension = int(self.model.get_sentence_embedding_dimension())

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.asarray(
            self.model.encode(
                texts,
                batch_size=self.batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
            ),
            dtype=np.float32,
        )


class _OpenAICompatibleEncoder:
    """Encoder for standard /v1/embeddings endpoints (OpenAI, Ollama, vLLM, TEI)."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "not-needed",
        model: str = "bge-m3",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        sample = self.encode(["dim probe"])
        self.dimension = int(sample.shape[1])

    def encode(self, texts: list[str]) -> np.ndarray:
        url = f"{self.base_url}/embeddings"
        payload = json.dumps({"model": self.model, "input": texts}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Failed to connect to embedding endpoint at {url}: {exc}") from exc

        raw = [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]
        vecs = np.asarray(raw, dtype=np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms = np.where(norms > 1e-9, norms, 1.0)
        return vecs / norms


def build_encoder(provider: str, model: str | None = None, revision: str | None = None,
                  *, device: str | None = None, batch_size: int = 64,
                  max_seq_length: int | None = None):
    if batch_size <= 0 or (max_seq_length is not None and max_seq_length <= 0):
        raise ValueError("Encoder batch size and sequence length must be positive")
    if provider == "sentence_transformers":
        model_name = model or "sentence-transformers/all-MiniLM-L6-v2"
        encoder = _SentenceTransformerEncoder(model_name=model_name, revision=revision)
        encoder.batch_size = batch_size
        if device is not None:
            encoder.model.to(device)
        if max_seq_length is not None:
            encoder.model.max_seq_length = max_seq_length
        return encoder
    if provider == "openai_compatible":
        model_name = model or "bge-m3"
        return _OpenAICompatibleEncoder(model=model_name)
    if provider == "hash":
        return _HashEncoder(dim=128)
    raise ValueError(f"Unknown embedding provider: {provider}")


_build_encoder = build_encoder


def _fetch_items_for_embedding(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Fetch item_id and formatted text; categories are sorted for deterministic output.

    Uses the same format_catalog_text() as pilot_item_embeddings so the full build
    produces vectors comparable to pilot quality estimates.
    Text protocol: title_store_main_category_categories_sorted_v2
    """
    # Fetch categories separately so we can sort them before formatting.
    cols = {row[1] for row in conn.execute("PRAGMA table_info(items)")}
    brand_expr = "brand" if "brand" in cols else "NULL AS brand"
    release_expr = "release_date" if "release_date" in cols else "NULL AS release_date"
    features_expr = "features" if "features" in cols else "NULL AS features"
    item_rows: dict[str, dict] = {}
    cur = conn.execute(
        f"SELECT item_id, title, store, main_category, {brand_expr}, {release_expr}, {features_expr} "
        "FROM items ORDER BY item_id"
    )
    for item_id, title, store, main_cat, brand, release_date, features in cur.fetchall():
        item_rows[str(item_id)] = {
            "title": title or "",
            "store": store or "",
            "main": main_cat or "",
            "brand": brand or "",
            "release_date": release_date or "",
            "features": features or "",
            "categories": [],
        }
    cur = conn.execute(
        "SELECT item_id, category FROM item_categories ORDER BY item_id, category"
    )
    for item_id, category in cur.fetchall():
        key = str(item_id)
        if key in item_rows:
            item_rows[key]["categories"].append(category)
    rows = []
    for item_id in sorted(item_rows):
        r = item_rows[item_id]
        text = format_catalog_text(
            r["title"],
            r["store"],
            r["main"],
            r["categories"],
            brand=r["brand"],
            release_date=r["release_date"],
            features=r["features"],
        )
        rows.append((item_id, text))
    return rows


def build_embeddings_for_corpus(
    sqlite_path: Path,
    output_npz_path: Path,
    provider: str = "hash",
    model: str | None = None,
    batch_size: int = 256,
    revision: str | None = None,
) -> None:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if not sqlite_path.exists():
        raise FileNotFoundError(f"Corpus SQLite database not found at {sqlite_path}")

    corpus_sha256 = file_hash(sqlite_path)
    print(f"Loading items from SQLite corpus: {sqlite_path}...")
    conn = sqlite3.connect(sqlite_path)
    try:
        items = _fetch_items_for_embedding(conn)
    finally:
        conn.close()

    total = len(items)
    print(f"Total catalog items to embed: {total}")
    if total == 0:
        print("Corpus is empty. Skipping embedding generation.")
        return

    item_ids = [item[0] for item in items]
    texts = [item[1] for item in items]

    encoder = _build_encoder(provider, model, revision=revision)
    print(f"Using encoder: {encoder.__class__.__name__} (dimension={encoder.dimension})")

    start_time = time.time()
    embeddings_list = []
    for i in range(0, total, batch_size):
        chunk = texts[i : i + batch_size]
        vecs = encoder.encode(chunk)
        embeddings_list.append(vecs)
        if (i // batch_size) % 10 == 0 or (i + batch_size >= total):
            processed = min(i + batch_size, total)
            elapsed = time.time() - start_time
            rate = processed / elapsed if elapsed > 0 else 0
            print(f"  Processed {processed}/{total} items ({rate:.1f} items/s)...")

    embeddings = np.vstack(embeddings_list)
    store = VectorStore(item_ids=item_ids, embeddings=embeddings)

    if file_hash(sqlite_path) != corpus_sha256:
        raise ValueError("Corpus changed during embedding build")
    resolved_model = model or {"hash": "sha256-token-hash-128-v1", "sentence_transformers": "sentence-transformers/all-MiniLM-L6-v2", "openai_compatible": "bge-m3"}[provider]
    probe = encoder.encode(["catalog retrieval encoder compatibility probe"])
    output_npz_path.parent.mkdir(parents=True, exist_ok=True)
    store.save(output_npz_path)
    meta_path = output_npz_path.with_suffix(".meta.json")
    meta_path.write_text(
        json.dumps({
            "provider": provider,
            "format_version": 1,
            "model": resolved_model,
            "revision": getattr(encoder, "revision", None),
            "encoder_probe": np.asarray(probe, dtype=np.float32).tolist(),
            "corpus_sha256": corpus_sha256,
            "artifact_sha256": file_hash(output_npz_path),
            "text_protocol": "title_store_main_category_categories_sorted_v2",
            "library_versions": {"numpy": np.__version__, **({"sentence-transformers": package_version("sentence-transformers")} if provider == "sentence_transformers" else {})},
            "experimental_hash_encoder": provider == "hash",
            "dimension": encoder.dimension,
            "count": len(store),
        }, indent=2),
        encoding="utf-8",
    )
    total_time = time.time() - start_time
    print(f"Done! Saved {len(store)} vectors to {output_npz_path} in {total_time:.2f}s.")


def load_validated_embeddings(path: Path, corpus_path: Path):
    """Require matching artifact, corpus and query encoder before evaluating hybrid."""
    path = Path(path)
    if path.is_dir():
        store = VectorStore.load(path)
        meta = store.artifact_metadata
        try:
            if file_hash(corpus_path) != meta['corpus_sha256']:
                raise ValueError('Embedding artifact/corpus checksum mismatch')
            if meta['text_protocol'] != 'title_store_main_category_categories_sorted_v2':
                raise ValueError('Unsupported full-catalog text protocol')
            encoder = build_encoder(meta['provider'], meta['model'], revision=meta['revision'],
                                    device=meta['device'], max_seq_length=meta['max_seq_length'])
            probe = np.asarray(encoder.encode(['catalog retrieval encoder compatibility probe']), dtype=np.float32)
            saved = np.asarray(meta['encoder_probe'], dtype=np.float32)
            if probe.shape != (1, store.dimension) or saved.shape != probe.shape or not np.allclose(probe, saved, rtol=1e-4, atol=1e-5):
                raise ValueError('Query encoder does not match catalog encoder')
        except Exception:
            store.item_ids._mmap.close()
            store.embeddings._mmap.close()
            raise
        return store, encoder, {**meta, 'path': str(path), 'metadata_sha256': file_hash(path / 'manifest.json')}
    meta_path = path.with_suffix(".meta.json")
    if not path.is_file() or not meta_path.is_file():
        raise ValueError("Embedding artifact/metadata missing; rebuild with build_item_embeddings.py")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    required = {"provider", "model", "revision", "encoder_probe", "corpus_sha256", "artifact_sha256", "dimension", "count", "text_protocol", "library_versions"}
    if meta.get("format_version") != 1 or required - meta.keys() or not meta.get("model"):
        raise ValueError("Embedding provenance incomplete; rebuild embeddings")
    if file_hash(path) != meta["artifact_sha256"] or file_hash(corpus_path) != meta["corpus_sha256"]:
        raise ValueError("Embedding artifact/corpus checksum mismatch; rebuild embeddings")
    if meta["provider"] == "sentence_transformers" and not meta["revision"]:
        raise ValueError("Embedding model revision missing")
    store = VectorStore.load(path)
    if store.dimension != meta["dimension"] or len(store) != meta["count"]:
        raise ValueError("Embedding dimension/count mismatch")
    if len(set(store.item_ids)) != len(store) or not np.isfinite(store.embeddings).all():
        raise ValueError("Embedding artifact contains duplicate IDs or non-finite vectors")
    encoder = build_encoder(meta["provider"], meta["model"], revision=meta["revision"])
    probe = np.asarray(encoder.encode(["catalog retrieval encoder compatibility probe"]), dtype=np.float32)
    saved_probe = np.asarray(meta["encoder_probe"], dtype=np.float32)
    if probe.shape != (1, store.dimension) or saved_probe.shape != probe.shape or not np.allclose(probe, saved_probe, rtol=1e-4, atol=1e-5):
        raise ValueError("Query encoder does not match catalog encoder")
    return store, encoder, {**meta, "path": str(path), "metadata_sha256": file_hash(meta_path)}


def main() -> None:
    ensure_utf8_stdout()
    parser = argparse.ArgumentParser(description="Build dense embeddings for item catalog")
    parser.add_argument("--domain", action="append", help="Domain name(s). Default: all domains (multi_domain)")
    parser.add_argument(
        "--provider",
        default="hash",
        choices=["hash", "sentence_transformers", "openai_compatible"],
        help="Embedding provider (default: hash for local test)",
    )
    parser.add_argument("--revision", help="Immutable model revision; resolved to HF commit SHA when omitted")
    parser.add_argument("--model", help="Embedding model name (e.g. sentence-transformers model)")
    parser.add_argument("--batch-size", type=int, default=256, help="Batch size for encoding (default: 256)")
    parser.add_argument("--tag", help="Explicit existing corpus bundle")
    args = parser.parse_args()

    paths = resolve_bundle_paths(tag=args.tag, domains=args.domain)
    tag = paths.tag
    corpus_sqlite = paths.corpus_dir / f"corpus_{tag}.sqlite"
    output_npz = paths.corpus_dir / f"item_embeddings_{tag}.npz"

    build_embeddings_for_corpus(
        sqlite_path=corpus_sqlite,
        output_npz_path=output_npz,
        provider=args.provider,
        model=args.model,
        batch_size=args.batch_size,
        revision=args.revision,
    )


if __name__ == "__main__":
    main()
