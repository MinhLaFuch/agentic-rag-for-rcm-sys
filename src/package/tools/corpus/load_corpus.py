"""Load ItemCorpus from SQLite file with validation."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path

from ._sql import get_corpus_schema_fingerprint, CORPUS_LOGIC_VERSION
from .item_corpus import ItemCorpus


def load_corpus(
    path: Path,
    meta_files: list[tuple[str, str]],
    item2id: dict[str, int],
    min_coverage: float,
) -> tuple[ItemCorpus, float]:
    """Load ItemCorpus from SQLite file with validation.

    Args:
        path: Path to the saved .sqlite file.
        meta_files: List of (domain, path) tuples for metadata files (for validation).
        item2id: Mapping from namespaced item_id to integer id (for validation).
        min_coverage: Minimum coverage threshold to validate against saved file.

    Returns:
        (corpus, coverage) where coverage is taken from the saved metadata.

    Raises:
        FileNotFoundError: If file or metadata file is missing.
        ValueError: If validation fails (schema mismatch, data hash mismatch, version mismatch, etc.).
    """
    t0 = time.perf_counter()

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Corpus file not found: {path}")
    meta_path = path.with_suffix(".meta.json")
    if not meta_path.exists():
        raise FileNotFoundError(f"Corpus metadata file not found: {meta_path}")

    # Load metadata
    with open(meta_path, encoding="utf-8") as f:
        metadata = json.load(f)

    # Validate format version
    if metadata.get("format_version") != 1:
        raise ValueError(
            f"Unsupported format version {metadata.get('format_version')}, expected 1. "
            "Re-build with --save-corpus to generate a new file."
        )

    # Validate schema fingerprint
    current_fingerprint = get_corpus_schema_fingerprint()
    saved_fingerprint = metadata["schema_fingerprint"]
    if current_fingerprint != saved_fingerprint:
        raise ValueError(
            "Schema fingerprint mismatch: corpus file was built with a different schema version. "
            "Re-build with --save-corpus."
        )

    # Validate logic version
    if metadata["logic_version"] != CORPUS_LOGIC_VERSION:
        raise ValueError(
            f"Logic version mismatch: saved {metadata['logic_version']}, current {CORPUS_LOGIC_VERSION}. "
            "Re-build with --save-corpus."
        )

    # Validate min_coverage
    if metadata["min_coverage"] != min_coverage:
        raise ValueError(
            f"min_coverage mismatch: saved {metadata['min_coverage']}, current {min_coverage}. "
            "Re-build with --save-corpus or adjust config."
        )

    # Validate source hashes
    current_hashes = []
    for domain, meta_path in meta_files:
        meta_path = Path(meta_path)
        if not meta_path.exists():
            raise FileNotFoundError(f"Meta file not found: {meta_path}")
        stat = meta_path.stat()
        file_key = f"{meta_path}:{stat.st_size}:{stat.st_mtime}"
        current_hashes.append(hashlib.sha256(file_key.encode("utf-8")).hexdigest())

    if current_hashes != metadata["source_hashes"]:
        raise ValueError(
            "Source file metadata mismatch: meta files have changed since corpus was saved. "
            "Re-build with --save-corpus."
        )

    # Validate mapping hash
    item_keys = sorted(item2id.keys())[:1000]
    current_mapping_hash = hashlib.sha256("".join(item_keys).encode("utf-8")).hexdigest()
    if current_mapping_hash != metadata["mapping_hash"]:
        raise ValueError(
            "Mapping hash mismatch: item2id has changed since corpus was saved. "
            "Re-build with --save-corpus."
        )

    # Validate num_items
    if len(item2id) != metadata["num_items"]:
        raise ValueError(
            f"num_items mismatch: saved {metadata['num_items']}, current {len(item2id)}. "
            "Re-build with --save-corpus."
        )

    # Load corpus using SQLite backup into memory
    # Step (g): backup
    t_backup = time.perf_counter()
    mem_conn = sqlite3.connect(":memory:")
    file_conn = sqlite3.connect(str(path))
    try:
        file_conn.backup(mem_conn)
        mem_conn.commit()
    finally:
        file_conn.close()

    backup_time = time.perf_counter() - t_backup
    print(f"  Corpus backup: {backup_time:.2f}s")

    # Validate table/index/FTS existence
    required_tables = ["items", "item_categories", "items_fts"]
    for table in required_tables:
        cur = mem_conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if cur.fetchone() is None:
            raise ValueError(f"Corpus file missing required table: {table}")

    # Check indexes exist
    required_indexes = ["idx_items_id", "idx_items_domain", "idx_cat_item"]
    for idx in required_indexes:
        cur = mem_conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name=?", (idx,))
        if cur.fetchone() is None:
            raise ValueError(f"Corpus file missing required index: {idx}")

    # Create ItemCorpus (this will set query_only and authorizer)
    corpus = ItemCorpus(mem_conn)

    load_time = time.perf_counter() - t0
    file_size_mb = path.stat().st_size / (1024 * 1024)
    print(f"  Corpus load total: {load_time:.2f}s ({file_size_mb:.1f} MB)")

    return corpus, metadata["coverage"]
