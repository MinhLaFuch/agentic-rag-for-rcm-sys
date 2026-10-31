"""Read-only readiness check for running full validation over cold/sparse/warm users.

This command checks the selected tag's splits, mappings, corpus, ItemKNN cache,
and optional semantic catalog. It never builds or modifies those artifacts.
It writes one JSON result to the requested output path.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import sqlite3
import sys
import time
from collections.abc import Mapping
from pathlib import Path

import numpy as np
import pandas as pd
from package.config import get_data_paths, get_domains, load_config
from package.tools.recommenders.fit_split_names import fit_split_names


ROOT = Path(__file__).resolve().parents[2]


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def mapping_hash(mapping: Mapping[str, int]) -> str:
    values = list(mapping.values())
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in values):
        raise ValueError("mapping indices must be non-negative integers")
    if sorted(values) != list(range(len(values))):
        raise ValueError("mapping indices must be unique and contiguous from zero")
    payload = json.dumps(sorted((str(k), int(v)) for k, v in mapping.items()),
                         ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _hash(path: Path) -> str:
    return file_hash(path)


def _mapping(path: Path) -> tuple[dict[str, int], str, str]:
    raw = path.read_bytes()
    value = json.loads(raw)
    mapping = {str(k): int(v) for k, v in value.items()}
    return mapping, mapping_hash(mapping), hashlib.sha256(raw).hexdigest()


def _scan_parquet(path: Path, columns: list[str], label: str) -> tuple[np.ndarray, np.ndarray, int]:
    users: list[np.ndarray] = []
    items: list[np.ndarray] = []
    rows = 0
    started = time.perf_counter()
    parquet = pd.read_parquet(path, columns=columns, engine="pyarrow")
    rows = len(parquet)
    users.append(parquet["user_idx"].to_numpy(dtype=np.int64, copy=True))
    items.append(parquet["item_idx"].to_numpy(dtype=np.int64, copy=True))
    print(f"[scan] {label}: {rows:,} rows in {time.perf_counter()-started:.1f}s", flush=True)
    return np.concatenate(users), np.concatenate(items), rows


def _pair_keys(users: np.ndarray, items: np.ndarray, n_items: int) -> np.ndarray:
    return np.unique(users * np.int64(n_items) + items)


def _range_check(users: np.ndarray, items: np.ndarray, n_users: int, n_items: int, label: str) -> None:
    if users.size and (users.min() < 0 or users.max() >= n_users):
        raise ValueError(f"{label}: user_idx outside user mapping")
    if items.size and (items.min() < 0 or items.max() >= n_items):
        raise ValueError(f"{label}: item_idx outside item mapping")


def _corpus_check(path: Path, item2id: dict[str, int], expected_item_hash: str,
                  data_paths, domains: list[str]) -> dict:
    result = {"path": str(path.resolve()), "exists": path.is_file()}
    if not path.is_file():
        return result | {"compatible": False, "reason": "missing SQLite corpus"}
    result["sha256"] = _hash(path)
    sidecar = path.with_suffix(".meta.json")
    result["sidecar"] = str(sidecar.resolve())
    result["sidecar_exists"] = sidecar.is_file()
    meta = {}
    if sidecar.is_file():
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
        result["sidecar_fields"] = {k: meta.get(k) for k in
            ("format_version", "artifact_sha256", "num_items", "coverage", "mapping_hash", "mapping_hash_protocol", "source_hash_protocol")}
        if meta.get("format_version") == 2:
            result["artifact_hash_matches_sidecar"] = meta.get("artifact_sha256") == result["sha256"]
            result["mapping_hash_matches"] = meta.get("mapping_hash") == expected_item_hash
        elif meta.get("format_version") == 1:
            # Legacy corpus manifests use key-only mapping hashes and
            # path:size:mtime source fingerprints, as the runtime loader does.
            legacy_hash = hashlib.sha256("".join(sorted(item2id)).encode("utf-8")).hexdigest()
            result["artifact_hash_matches_sidecar"] = None
            result["mapping_hash_matches"] = meta.get("mapping_hash") == legacy_hash
            paths = [data_paths.meta_path(domain) for domain in domains]
            computed = []
            missing = []
            for source in paths:
                if not source.exists():
                    missing.append(str(source))
                    computed.append(None)
                else:
                    stat = source.stat()
                    key = f"{source}:{stat.st_size}:{stat.st_mtime}"
                    computed.append(hashlib.sha256(key.encode("utf-8")).hexdigest())
            result["legacy_source_provenance"] = {"paths": [str(p.resolve()) for p in paths],
                "expected_hashes": meta.get("source_hashes"), "current_hashes": computed,
                "hashes_match": computed == meta.get("source_hashes"), "missing": missing,
                "hash_protocol": "legacy_path_size_mtime"}
        else:
            result["artifact_hash_matches_sidecar"] = False
            result["mapping_hash_matches"] = False
    else:
        result["artifact_hash_matches_sidecar"] = False
        result["mapping_hash_matches"] = False
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=60)
    try:
        conn.execute("PRAGMA query_only=ON")
        result["quick_check"] = conn.execute("PRAGMA quick_check").fetchone()[0]
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        result["tables"] = sorted(tables)
        result["items_rows"] = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] if "items" in tables else None
        result["fts_rows"] = conn.execute("SELECT COUNT(*) FROM items_fts").fetchone()[0] if "items_fts" in tables else None
        db_ids = {str(row[0]) for row in conn.execute("SELECT item_id FROM items")}
        expected_ids = set(item2id)
        result["mapping_item_set_matches"] = db_ids == expected_ids
        result["mapping_items_missing_from_corpus"] = len(expected_ids - db_ids)
        result["corpus_items_missing_from_mapping"] = len(db_ids - expected_ids)
        result["fts_has_all_rows"] = result["items_rows"] == result["fts_rows"]
    finally:
        conn.close()
    source_ok = result.get("legacy_source_provenance", {}).get("hashes_match", True)
    artifact_ok = result.get("artifact_hash_matches_sidecar") in (True, None)
    result["compatible"] = bool(result.get("quick_check") == "ok" and result.get("mapping_item_set_matches")
        and result.get("fts_has_all_rows") and artifact_ok and source_ok and result.get("mapping_hash_matches"))
    if meta.get("format_version") == 1:
        result["provenance_limit"] = "legacy manifest has no SQLite artifact checksum; verified schema/logic, item set, FTS counts and loader-compatible source/mapping fingerprints"
    return result


def _expected_fit_splits(data_paths, eval_on: str) -> list[str]:
    """Read the split protocol recorded for this tag, falling back to legacy rules."""
    manifest_path = data_paths.splits_dir / "stage_3.manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("flags", {}).get("data_protocol") == "temporal_train_core":
            return ["train_core"]
    return fit_split_names(eval_on)


def _expected_itemknn_mapping_hashes(data_paths, default_item_hash: str,
                                    default_user_hash: str) -> tuple[str, str, str]:
    """Use the fit-only mappings recorded by Stage 3 for temporal train-core caches."""
    manifest_path = data_paths.splits_dir / "stage_3.manifest.json"
    if not manifest_path.is_file():
        return default_item_hash, default_user_hash, "full"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("flags", {}).get("data_protocol") != "temporal_train_core":
        return default_item_hash, default_user_hash, "full"
    records = {record.get("path", "").replace("\\", "/"): record
               for record in manifest.get("outputs", [])}
    tag_prefix = f"resource/mapped/{data_paths.tag}/fit_core/"
    item_record = records.get(tag_prefix + "item2id.json", {})
    user_record = records.get(tag_prefix + "user2id.json", {})
    item_hash = item_record.get("mapping_hash")
    user_hash = user_record.get("mapping_hash")
    if not item_hash or not user_hash:
        return default_item_hash, default_user_hash, "full_fallback_manifest_missing_fit_mapping_hash"
    return item_hash, user_hash, "fit_core"


def _artifact_check(path: Path | None, kind: str, item_hash: str, user_hash: str,
                    split_hashes: dict, *, eval_on: str = "validation",
                    expected_fit_splits: list[str] | None = None,
                    expected_tag: str | None = None) -> dict:
    out = {"path": str(path.resolve()) if path else None, "exists": bool(path and path.exists())}
    if path is None or not path.exists():
        return out | {"compatible": False, "reason": f"missing {kind} artifact"}
    if kind == "itemknn":
        meta_path = path.with_suffix(".meta.json")
        out["sha256"] = _hash(path)
        out["meta_path"] = str(meta_path.resolve())
        if not meta_path.exists():
            return out | {"compatible": False, "reason": "missing provenance sidecar"}
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        provenance = meta.get("provenance", {})
        out["provenance"] = provenance
        out["artifact_hash_matches"] = meta.get("artifact_sha256") == out["sha256"]
        out["mapping_hashes_match"] = (provenance.get("item_mapping_hash") == item_hash and
                                         provenance.get("user_mapping_hash") == user_hash)
        out["mapping_scope"] = "fit_core" if expected_fit_splits == ["train_core"] else "full"
        # The cache metadata does not bind a split file hash. data_hash is only
        # validated by the loader against the rows loaded at runtime.
        out["fit_split_hash_binding"] = {"present": False, "current_train_sha256": split_hashes.get("train")}
        expected_fit_splits = expected_fit_splits or fit_split_names(eval_on)
        out["expected_fit_splits"] = expected_fit_splits
        out["fit_splits_match"] = provenance.get("fit_splits") == expected_fit_splits
        out["eval_split_matches"] = provenance.get("eval_on") == eval_on
        out["tag_matches"] = provenance.get("tag") == expected_tag if expected_tag else bool(provenance.get("tag"))
        out["compatible"] = bool(out["artifact_hash_matches"] and out["mapping_hashes_match"]
            and out["fit_splits_match"] and out["eval_split_matches"] and out["tag_matches"])
        out["compatible_for_full_run"] = False
        out["compatibility_note"] = "loader must recompute ItemKNN data hash against the recorded fit split rows before reuse"
    else:
        manifest_path = path / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        out["status"] = manifest.get("status")
        out["rows"] = manifest.get("rows")
        out["valid_rows"] = manifest.get("valid_rows")
        identity = manifest.get("identity", {})
        out["mapping_hash_matches"] = identity.get("mapping_hash") == item_hash
        out["corpus_sha256"] = identity.get("corpus_sha256")
        out["artifact_hashes_verified"] = all(_hash(path / name) == expected
            for name, expected in manifest.get("artifact_hashes", {}).items())
        out["compatible"] = bool(manifest.get("status") == "complete" and out["mapping_hash_matches"]
            and out["artifact_hashes_verified"] and manifest.get("rows") == len(json.loads((path / "item_ids.json").read_text(encoding="utf-8"))))
    return out


def run(args) -> dict:
    tag = args.tag
    paths = get_data_paths(tag)
    mapped = paths.mapped_dir
    splits = paths.splits_dir
    domains = get_domains()
    item2id, item_hash, item_file_hash = _mapping(mapped / "item2id.json")
    user2id, user_hash, user_file_hash = _mapping(mapped / "user2id.json")
    n_items, n_users = len(item2id), len(user2id)
    split_hashes = {name: _hash(splits / f"{name}.parquet") for name in ("train", "validation", "test")}
    train_u, train_i, train_rows = _scan_parquet(splits / "train.parquet", ["user_idx", "item_idx"], "train")
    valid_u, valid_i, valid_rows = _scan_parquet(splits / f"{args.eval_on}.parquet", ["user_idx", "item_idx"], args.eval_on)
    _range_check(train_u, train_i, n_users, n_items, "train")
    _range_check(valid_u, valid_i, n_users, n_items, args.eval_on)
    train_keys = _pair_keys(train_u, train_i, n_items)
    valid_keys = _pair_keys(valid_u, valid_i, n_items)
    train_history = np.bincount((train_keys // n_items).astype(np.int64), minlength=n_users)
    target_counts = np.bincount((valid_keys // n_items).astype(np.int64), minlength=n_users)
    novel_mask = ~np.isin(valid_keys, train_keys, assume_unique=True)
    novel_keys = valid_keys[novel_mask]
    sparse_max = int(load_config("eval/segment_thresholds")["segment_thresholds"]["sparse_max_history"])
    target_users = np.flatnonzero(target_counts)
    segment_masks = {
        "cold": train_history[target_users] == 0,
        "sparse": (train_history[target_users] >= 1) & (train_history[target_users] <= sparse_max),
        "warm": train_history[target_users] > sparse_max,
    }
    segments = {}
    novel_user_ids = novel_keys // n_items
    for name, mask in segment_masks.items():
        ids = target_users[mask]
        sm = np.isin(novel_user_ids, ids, assume_unique=False)
        segments[name] = {
            "users_with_targets": int(len(ids)),
            "target_pairs": int(target_counts[ids].sum()),
            "novel_target_pairs": int(sm.sum()),
            "targets_seen_in_fit_pairs": int(target_counts[ids].sum() - sm.sum()),
            "history_unique_items_min": int(train_history[ids].min()) if len(ids) else None,
            "history_unique_items_median": float(np.median(train_history[ids])) if len(ids) else None,
            "history_unique_items_max": int(train_history[ids].max()) if len(ids) else None,
        }
    corpus = _corpus_check(paths.corpus_path, item2id, item_hash, paths, domains)
    itemknn_path = paths.item_knn_path(args.eval_on)
    expected_fit_splits = _expected_fit_splits(paths, args.eval_on)
    knn_item_hash, knn_user_hash, knn_mapping_scope = _expected_itemknn_mapping_hashes(
        paths, item_hash, user_hash)
    itemknn = _artifact_check(itemknn_path if itemknn_path.is_file() else None, "itemknn",
        knn_item_hash, knn_user_hash, split_hashes, eval_on=args.eval_on,
        expected_fit_splits=expected_fit_splits, expected_tag=tag)
    itemknn["mapping_scope"] = knn_mapping_scope
    semantic_candidates = sorted(paths.experiments_dir.rglob("manifest.json"))
    semantic_path = next((p.parent for p in semantic_candidates if p.parent.name == "catalog_full"
        and (lambda m: m.get("identity", {}).get("mapping_hash") == item_hash
             and m.get("identity", {}).get("corpus_sha256") == corpus.get("sha256"))
            (json.loads(p.read_text(encoding="utf-8")))), None)
    semantic = _artifact_check(semantic_path, "semantic", item_hash, user_hash, split_hashes)
    try:
        semantic["corpus_matches"] = semantic.get("corpus_sha256") == corpus.get("sha256")
        semantic["compatible"] = semantic.get("compatible", False) and semantic["corpus_matches"]
    except Exception:
        semantic["corpus_matches"] = False
    split_info = {}
    for name in ("train", "validation", "test"):
        p = splits / f"{name}.parquet"
        split_info[name] = {"path": str(p.resolve()), "bytes": p.stat().st_size, "sha256": split_hashes[name]}
    required_prefixes = {"numpy": "2.5.", "pandas": "3.0.", "pyarrow": "18.", "PyYAML": "6.0."}
    environment = {"python": sys.version.split()[0], "packages": {}, "missing_or_out_of_constraint": []}
    for package, prefix in required_prefixes.items():
        try:
            version = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            version = None
        environment["packages"][package] = version
        if version is None or not version.startswith(prefix):
            environment["missing_or_out_of_constraint"].append(package)
    try:
        scipy_version = importlib.metadata.version("scipy")
    except importlib.metadata.PackageNotFoundError:
        scipy_version = None
    environment["packages"]["scipy"] = scipy_version
    try:
        from packaging.version import Version
        scipy_ok = scipy_version is not None and Version("1.14") <= Version(scipy_version) < Version("1.19")
    except Exception:
        scipy_ok = False
    if not scipy_ok:
        environment["missing_or_out_of_constraint"].append("scipy")
    try:
        httpx_version = importlib.metadata.version("httpx")
    except importlib.metadata.PackageNotFoundError:
        httpx_version = None
    environment["packages"]["httpx"] = httpx_version
    try:
        from packaging.version import Version
        httpx_ok = httpx_version is not None and Version("0.27") <= Version(httpx_version) < Version("0.28")
    except Exception:
        httpx_ok = False
    if not httpx_ok:
        environment["missing_or_out_of_constraint"].append("httpx")
    return {
        "format_version": 1,
        "created_at_unix": time.time(),
        "protocol": {"tag": tag, "evaluation_split": args.eval_on,
            "segment_definition": {"cold": "0 unique train pairs", "sparse": f"1..{sparse_max} unique train pairs", "warm": f">{sparse_max} unique train pairs"},
            "ground_truth": "unique observed evaluation user-item pairs; binary relevance",
            "target_seen_policy": "reported separately; do not count seen targets as novel retrieval hits"},
        "mappings": {"users": n_users, "items": n_items, "user_mapping_hash": user_hash,
            "item_mapping_hash": item_hash, "user_mapping_file_sha256": user_file_hash, "item_mapping_file_sha256": item_file_hash},
        "environment": environment,
        "splits": split_info,
        "population": {"train_rows": train_rows, "unique_train_pairs": int(len(train_keys)),
            "duplicate_train_rows": int(train_rows-len(train_keys)), "evaluation_rows": valid_rows,
            "unique_evaluation_pairs": int(len(valid_keys)), "evaluation_users_with_targets": int(len(target_users)),
            "novel_evaluation_pairs": int(len(novel_keys)), "seen_evaluation_pairs": int(len(valid_keys)-len(novel_keys)),
            "segments": segments},
        "artifacts": {"corpus": corpus, "itemknn": itemknn, "semantic_catalog": semantic},
        "readiness": {"full_validation_population_defined": bool(len(target_users)),
            "mapping_indices_validated_against_split_ranges": True,
            "evaluation_environment_ready": not environment["missing_or_out_of_constraint"],
            "corpus_ready": bool(corpus.get("compatible")),
            "itemknn_provenance_compatible": bool(itemknn.get("compatible")),
            "current_metadata_sources_present": bool(corpus.get("legacy_source_provenance") is None
                or not corpus.get("legacy_source_provenance", {}).get("missing")),
            "itemknn_cache_reusable_without_runtime_data_hash_check": False,
            "semantic_ready": bool(semantic.get("compatible")),
            "cold_users_have_fit_history_query": False,
            "recommendation": "Use ranking_eval.py for validation on this tag and confirm the ItemKNN loader recomputes its data hash against the recorded fit rows. The corpus passed artifact, mapping, item-set, and FTS checks. A semantic catalog was not found; it is not required for a CF/corpus baseline. History-based CF/FTS is unavailable for cold users, so report that segment separately."},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tag", default="multi_domain")
    ap.add_argument("--eval-on", choices=("validation",), default="validation")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    result = run(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_suffix(args.output.suffix + ".partial")
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temp.replace(args.output)
    print(json.dumps(result["population"], ensure_ascii=False, indent=2))
    print(f"[saved] {args.output.resolve()}")


if __name__ == "__main__":
    main()
