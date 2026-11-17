"""Convert a completed format-B full-catalog artifact into format-A semantic artifacts.

Format B (build_full_item_embeddings.py): manifest.json + vectors.npy + item_ids.npy.
Format A (build_dense_retrieval.py):    manifest.json + documents.jsonl + item_ids.json
                                       + vectors.npy + valid.npy + encoder lock (pin).

The converter does NOT re-encode anything: vectors are copied byte-for-byte and
valid.npy is all-True (the full builder already verified finite normalized rows).
documents.jsonl is regenerated from the corpus with the SAME text protocol the
full builder used (title_store_main_category_categories_sorted_v2) so the file
honestly records what was encoded. item_id order is asserted identical to the
artifact's item_ids.npy while streaming the corpus.

Usage (from src/, .venv-semantic or any env with numpy):
    python scripts/data_pipeline/convert_full_to_semantic_artifacts.py \
        --tag multi_domain \
        --source-dir experiments/embedding_builds/multi_domain_full \
        --out-dir experiments/embedding_builds/multi_domain_semantic
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from pathlib import Path

import numpy as np

from package.config.resolve_bundle_paths import resolve_bundle_paths
from package.embeddings.read_catalog_text_chunk import read_catalog_text_chunk


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _atomic_json(path: Path, value) -> None:
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def convert(args) -> None:
    source = Path(args.source_dir)
    out = Path(args.out_dir)
    if out.exists():
        raise ValueError(f"output dir already exists: {out}")

    # --- verify source is a completed format-B artifact ---------------------
    meta = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if (meta.get("format_version") != 2 or meta.get("status") != "complete"
            or meta.get("kind") != "full_catalog_embeddings" or meta.get("partial_catalog") is not False):
        raise ValueError("source is not a completed full-catalog embedding artifact")
    count = int(meta["count"])
    dimension = int(meta["dimension"])

    ids_mm = np.load(source / "item_ids.npy", mmap_mode="r")
    vectors_mm = np.load(source / "vectors.npy", mmap_mode="r")
    if ids_mm.shape != (count,) or vectors_mm.shape != (count, dimension) or vectors_mm.dtype != np.float32:
        raise ValueError("source artifact shape/dtype mismatch")

    paths = resolve_bundle_paths(tag=args.tag)
    conn = sqlite3.connect(paths.corpus_path.resolve().as_uri() + "?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")

    out.mkdir(parents=True)
    try:
        # --- stream corpus in canonical order; assert id sequence matches ---
        position = 0
        last_id = None
        doc_tmp = out / "documents.jsonl.tmp"
        ids_tmp = out / "item_ids.json.tmp"
        with doc_tmp.open("w", encoding="utf-8") as docs, ids_tmp.open("w", encoding="utf-8") as ids_file:
            ids_file.write("[")
            first = True
            while True:
                chunk = read_catalog_text_chunk(conn, last_id, args.chunk_size)
                if not chunk:
                    break
                for item_id, text in chunk:
                    if position >= count or str(ids_mm[position]) != item_id:
                        raise ValueError(
                            f"item_id order mismatch at row {position}: "
                            f"artifact={ids_mm[position]!r} corpus={item_id!r}"
                        )
                    docs.write(json.dumps({"item_id": item_id, "text": text, "valid": True},
                                          ensure_ascii=False) + "\n")
                    ids_file.write(("" if first else ",") + json.dumps(item_id, ensure_ascii=False))
                    first = False
                    position += 1
                    last_id = item_id
                print(f"[convert] {position:,}/{count:,} rows", flush=True)
            ids_file.write("]")
        conn.close()
        if position != count:
            raise ValueError(f"corpus yielded {position} items but artifact has {count}")

        doc_tmp.replace(out / "documents.jsonl")
        ids_tmp.replace(out / "item_ids.json")

        # --- copy vectors byte-for-byte; valid mask all True ----------------
        shutil.copyfile(source / "vectors.npy", out / "vectors.npy")
        valid = np.lib.format.open_memmap(out / "valid.npy", mode="w+", dtype=np.bool_, shape=(count,))
        valid[:] = True
        valid.flush()
        del valid

        # --- format-A manifest ------------------------------------------------
        artifacts = {name: _sha256(out / name)
                     for name in ("documents.jsonl", "item_ids.json", "vectors.npy", "valid.npy")}
        identity = {
            "format_version": 1,
            "converted_from": {
                "kind": "full_catalog_embeddings",
                "source_dir": str(source),
                "source_manifest_sha256": _sha256(source / "manifest.json"),
                "source_build_id": meta.get("build_id"),
            },
            "dimensions": dimension,
            "dtype": "float32",
            "normalized": True,
            "model_id": meta.get("model"),
            "revision": meta.get("revision"),
            "text_protocol": meta.get("text_protocol") or "title_store_main_category_categories_sorted_v2",
            "max_seq_length": meta.get("max_seq_length", 256),
            "seed": 42,
            "batch_size": (meta.get("identity") or {}).get("batch_size"),
            "chunk_size": (meta.get("identity") or {}).get("chunk_size"),
        }
        _atomic_json(out / "manifest.json", {
            "identity": identity,
            "rows": count,
            "valid_rows": count,
            "invalid_rows": 0,
            "artifact_hashes": artifacts,
            "item_id_row_order_sha256": artifacts["item_ids.json"],
            "invalid_row_policy": "no invalid rows; converted from verified full-build artifact (all vectors finite/normalized)",
            "status": "complete",
            "quality_evaluated": False,
            "conversion": {
                "tool": "scripts/data_pipeline/convert_full_to_semantic_artifacts.py",
                "tag": args.tag,
                "vectors_copied_not_reencoded": True,
            },
        })
        print(f"[done] format-A artifacts -> {out}", flush=True)
    except Exception:
        conn.close()
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--source-dir", type=Path, required=True,
                        help="Completed format-B output dir (manifest.json, vectors.npy, item_ids.npy)")
    parser.add_argument("--out-dir", type=Path, required=True,
                        help="New format-A output dir (must not exist)")
    parser.add_argument("--chunk-size", type=int, default=4096)
    args = parser.parse_args()
    convert(args)


if __name__ == "__main__":
    sys.exit(main())
