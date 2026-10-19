"""Save ItemCorpus to SQLite file for later reuse."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path

from ._sql import get_corpus_schema_fingerprint, CORPUS_LOGIC_VERSION
from .item_corpus import ItemCorpus


def save_corpus(
    corpus: ItemCorpus,
    path: Path,
    meta_files: list[tuple[str, str]],
    item2id: dict[str, int],
    min_coverage: float,
    coverage: float,
    build_times: dict[str, float],
) -> float:
    """Save ItemCorpus to SQLite file with metadata validation.

    Args:
        corpus: ItemCorpus instance to save.
        path: Destination path for the .sqlite file.
        meta_files: List of (domain, path) tuples for metadata files.
        item2id: Mapping from namespaced item_id to integer id.
        min_coverage: Minimum coverage threshold used during build.
        coverage: Actual coverage achieved during build.
        build_times: Timing information for each build step.

    Returns:
        Time taken to save in seconds.

    Raises:
        ValueError: If corpus connection is not valid.
    """
    t0 = time.perf_counter()

    if not hasattr(corpus, "_conn") or corpus._conn is None:
        raise ValueError("Corpus has no valid connection")

    # Compute source file metadata hash
    source_hashes = []
    for domain, meta_path in meta_files:
        meta_path = Path(meta_path)
        if not meta_path.exists():
            raise FileNotFoundError(f"Meta file not found: {meta_path}")
        stat = meta_path.stat()
        # Hash path + size + mtime to detect changes
        file_key = f"{meta_path}:{stat.st_size}:{stat.st_mtime}"
        source_hashes.append(hashlib.sha256(file_key.encode("utf-8")).hexdigest())

    # Compute item2id hash (fast: hash sorted keys by first 1000 items)
    item_keys = sorted(item2id.keys())[:1000]
    mapping_hash = hashlib.sha256("".join(item_keys).encode("utf-8")).hexdigest()

    # Build metadata
    metadata = {
        "format_version": 1,
        "schema_fingerprint": get_corpus_schema_fingerprint(),
        "logic_version": CORPUS_LOGIC_VERSION,
        "num_items": len(item2id),
        "min_coverage": min_coverage,
        "coverage": coverage,
        "source_hashes": source_hashes,
        "mapping_hash": mapping_hash,
        "build_times": build_times,
        "created_at": time.time(),
    }

    # Write files
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")

    # Save using SQLite backup API
    src_conn = corpus._conn
    dst_conn = sqlite3.connect(str(tmp_path))
    try:
        src_conn.backup(dst_conn)
        dst_conn.commit()
    finally:
        dst_conn.close()

    # Write metadata
    meta_path = path.with_suffix(".meta.json")
    with open(str(meta_path.with_suffix(".tmp.json")), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    # Atomic rename
    tmp_path.replace(path)
    meta_path.with_suffix(".tmp.json").replace(meta_path)

    save_time = time.perf_counter() - t0
    file_size_mb = path.stat().st_size / (1024 * 1024)
    print(f"  Corpus save: {save_time:.2f}s ({file_size_mb:.1f} MB)")

    return save_time
