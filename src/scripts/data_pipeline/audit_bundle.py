"""Read-only P0 audit: separate artifact integrity, config drift and protocol readiness.

Only the requested JSON report and temporary split-audit database are written.
This command never repairs manifests or changes pipeline artifacts/configuration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
import time
from contextlib import closing
from pathlib import Path, PureWindowsPath

import numpy as np
import pyarrow.parquet as pq

from package.config import PROJECT_ROOT, get_domains, load_config
from package.config.resolve_bundle_paths import resolve_bundle_paths
from package.data.manifest.load_audit_profile import load_audit_profile
from package.corpus import CORPUS_LOGIC_VERSION, get_corpus_schema_fingerprint
from package.recommenders.shared import mapping_hash
from package.utils import ensure_utf8_stdout


def _contained(root: Path, relative: str) -> Path:
    if Path(relative).is_absolute() or PureWindowsPath(relative).is_absolute():
        raise ValueError(f"Absolute manifest path: {relative}")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Manifest path escapes project: {relative}")
    return path


def _scan_splits(paths, item_count, user_count, scratch_dir):
    """Stream bounds and event-overlap checks; store keys on disk, not Python sets."""
    result = {}
    with tempfile.TemporaryDirectory(prefix="bundle-split-audit-", dir=scratch_dir) as temp:
        # Connection.__exit__ only commits/rolls back; it does not close the DB.
        # Close before TemporaryDirectory attempts cleanup on Windows.
        with closing(sqlite3.connect(Path(temp) / "events.sqlite")) as conn:
            conn.execute("CREATE TABLE events (u INTEGER, i INTEGER, t INTEGER, s INTEGER, PRIMARY KEY(u,i,t,s)) WITHOUT ROWID")
            for split_id, split in enumerate(("train", "validation", "test")):
                rows, low, high = 0, None, None
                with closing(pq.ParquetFile(paths.split_path(split))) as parquet:
                    for batch in parquet.iter_batches(batch_size=100_000, columns=["user_idx", "item_idx", "timestamp"]):
                        arrays = []
                        for column in batch.columns:
                            if column.null_count:
                                raise ValueError(f"Null indices/timestamps in {split}")
                            values = column.to_numpy(zero_copy_only=False)
                            if not np.issubdtype(values.dtype, np.integer):
                                raise ValueError(f"Expected integer indices/timestamps in {split}")
                            arrays.append(values)
                        users, items, timestamps = arrays
                        if not len(users):
                            continue
                        if users.min() < 0 or users.max() >= user_count or items.min() < 0 or items.max() >= item_count:
                            raise ValueError(f"Out-of-mapping index in {split}")
                        low = min(low, int(timestamps.min())) if low is not None else int(timestamps.min())
                        high = max(high, int(timestamps.max())) if high is not None else int(timestamps.max())
                        conn.executemany("INSERT OR IGNORE INTO events VALUES (?,?,?,?)",
                                         ((int(u), int(i), int(t), split_id) for u, i, t in zip(*arrays)))
                        conn.commit()
                        rows += len(users)
                        print(f"[splits] {split}: {rows:,}/{parquet.metadata.num_rows:,} events", flush=True)
                if not rows:
                    raise ValueError(f"Empty split: {split}")
                result[split] = {"rows": rows, "min_timestamp": low, "max_timestamp": high}
            overlap = conn.execute("SELECT COUNT(*) FROM (SELECT u,i,t FROM events GROUP BY u,i,t HAVING COUNT(*) > 1)").fetchone()[0]
    result["overlapping_events"] = overlap
    result["temporal_order_valid"] = (
        result["train"]["max_timestamp"] < result["validation"]["min_timestamp"]
        and result["validation"]["max_timestamp"] < result["test"]["min_timestamp"]
    )
    return result


def audit_bundle(paths, *, root=PROJECT_ROOT, scan_splits=False, scratch_dir=None):
    """Return evidence and blockers; config drift never becomes an artifact MATCH."""
    root = Path(root).resolve()
    report = {"tag": paths.tag, "artifact_checks": [], "config_checks": [],
              "manifests": [], "blockers": [], "warnings": [], "split_scan": {"status": "not_run"}}
    profile = load_audit_profile(paths, project_root=root)
    report["audit_profile"] = profile
    cache = {}

    def digest(path):
        path = Path(path).resolve()
        if not path.is_file():
            return "MISSING"
        before = path.stat()
        identity = (str(path), before.st_size, before.st_mtime_ns)
        if identity not in cache:
            print(f"[sha256] {path} ({before.st_size / 1024**2:.1f} MiB)", flush=True)
            h = hashlib.sha256()
            tick = time.monotonic()
            processed = 0
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                    h.update(chunk)
                    processed += len(chunk)
                    if time.monotonic() - tick >= 10:
                        print(f"  {processed / 1024**2:.0f}/{before.st_size / 1024**2:.0f} MiB", flush=True)
                        tick = time.monotonic()
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError(f"File changed during audit: {path}")
            cache[identity] = h.hexdigest()
        return cache[identity]

    def check(relative, expected, manifest, target_list, external=False, historical=False):
        evidence_root = Path(profile["historical_config_root"]) if historical and profile else root
        path = _contained(evidence_root, relative)
        actual = "UNVERIFIED_EXTERNAL" if external else digest(path)
        status = "MATCH" if actual == expected else ("UNVERIFIED_EXTERNAL" if external else "MISMATCH")
        target_list.append({"path": relative, "manifest": str(manifest), "expected_sha256": expected,
                            "actual_sha256": actual, "status": status,
                            "evidence_path": str(path),
                            **({"current_runtime_file_sha256": digest(_contained(root, relative))} if historical else {})})
        print(f"[{status}] {relative}", flush=True)

    stage2_path = paths.filtered_path.parent / "stage_2.manifest.json"
    stage2 = json.loads(stage2_path.read_text(encoding="utf-8")) if stage2_path.is_file() else {}
    domains = stage2.get("flags", {}).get("domains", get_domains())
    if set(domains) != set(get_domains()):
        # Single-domain bundles are valid, but runtime selection must be explicit.
        report["warnings"].append("Bundle domain set differs from current full-domain configuration")
    expected = [(paths.stage1_manifest_path(domain), "clean_domain") for domain in domains]
    expected += [(stage2_path, "merge_filter_domains"), (paths.splits_dir / "stage_3.manifest.json", "map_split"),
                 (paths.corpus_dir / "stage_4.manifest.json", "build_artifacts")]
    documents = {}
    for path, stage in expected:
        if not path.is_file():
            report["blockers"].append(f"Missing manifest: {path}")
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        documents[stage] = doc
        report["manifests"].append({"path": str(path), "sha256": digest(path), "stage": doc.get("stage"), "tag": doc.get("tag")})
        if doc.get("schema_version") != 1 or doc.get("tag") != paths.tag or doc.get("stage") != stage:
            report["blockers"].append(f"Manifest identity/schema mismatch: {path}")
        for record in doc.get("inputs", []) + doc.get("outputs", []) + doc.get("upstream_manifests", []):
            check(record["path"], record["sha256"], path, report["artifact_checks"], record.get("external", False))
        for relative, expected_hash in doc.get("config_sha256", {}).items():
            check(relative, expected_hash, path, report["config_checks"], historical=True)
        report["warnings"].extend(doc.get("warnings", []))

    required_outputs = {
        "merge_filter_domains": [paths.filtered_path],
        "map_split": [paths.mapped_dir / "item2id.json", paths.mapped_dir / "user2id.json",
                      *(paths.split_path(name) for name in ("train", "validation", "test"))],
        "build_artifacts": [paths.corpus_path, paths.corpus_path.with_suffix(".meta.json")],
    }
    for stage, required_paths in required_outputs.items():
        declared = {_contained(root, row["path"]) for row in documents.get(stage, {}).get("outputs", [])}
        for path in required_paths:
            if path.resolve() not in declared:
                report["blockers"].append(f"Selected artifact not attested by {stage}: {path}")

    if any(row["status"] != "MATCH" for row in report["artifact_checks"]):
        report["blockers"].append("Artifact/source/upstream integrity failed or includes unverifiable external paths")
    drift = [row for row in report["config_checks"] if row["status"] != "MATCH"]
    report["config_drift"] = sorted({row["path"] for row in report["config_checks"]
                                    if row["current_runtime_file_sha256"] != row["expected_sha256"]})
    if profile and not drift and report["config_drift"]:
        report["warnings"].append("Historical snapshots verified; current runtime configs differ and are validated separately by audit profile")
    if drift:
        report["blockers"].append("Historical config drift requires snapshot verification and runtime compatibility review")

    stage3 = documents.get("map_split", {})
    flags = stage3.get("flags", {})
    runtime_split = load_config("data/split")["split"]
    report["protocol"] = {"recorded": flags.get("data_protocol"), "stage3_flags": flags,
                          "runtime_split": runtime_split, "historical_config_verified": not bool(drift)}
    if flags.get("data_protocol") != runtime_split.get("data_protocol", "legacy_kcore_before_split"):
        report["blockers"].append("Recorded data protocol differs from current runtime split configuration")
    if flags.get("data_protocol") == "temporal_train_core":
        runtime_cutoffs = runtime_split.get("temporal_train_core", {})
        if (flags.get("cutoff_1"), flags.get("cutoff_2")) != (
            runtime_cutoffs.get("train_end_inclusive_ms"), runtime_cutoffs.get("validation_end_inclusive_ms")
        ):
            report["blockers"].append("Recorded cutoffs differ from current runtime split configuration")

    mapping_path = paths.mapped_dir / "item2id.json"
    meta_path = paths.corpus_path.with_suffix(".meta.json")
    if mapping_path.is_file() and meta_path.is_file() and paths.corpus_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
        indices = list(mapping.values())
        if any(type(v) is not int for v in indices) or set(indices) != set(range(len(mapping))):
            report["blockers"].append("Item mapping indices must be unique and contiguous")
        item_count = len(mapping)
        actual_mapping_hash = mapping_hash(mapping)
        del mapping, indices
        if meta.get("mapping_hash") != actual_mapping_hash or meta.get("num_items") != item_count:
            report["blockers"].append("Corpus mapping hash/count mismatch")
        if meta.get("format_version") != 2 or meta.get("logic_version") != CORPUS_LOGIC_VERSION or meta.get("schema_fingerprint") != get_corpus_schema_fingerprint():
            report["blockers"].append("Corpus format/logic/schema incompatible with current loader")
        if meta.get("first_seen_protocol") != "minimum_timestamp_per_namespaced_item_in_all_cleaned_interactions_v1":
            report["blockers"].append("Corpus lacks the required first_seen provenance protocol")
        if digest(paths.corpus_path) != meta.get("artifact_sha256"):
            report["blockers"].append("Corpus checksum differs from corpus sidecar")
        with closing(sqlite3.connect(paths.corpus_path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
            if not {"items", "item_categories", "items_fts"}.issubset(tables) or not {"idx_items_id", "idx_items_domain", "idx_cat_item"}.issubset(indexes):
                report["blockers"].append("Corpus missing required tables/indexes")
            columns = {row[1] for row in conn.execute("PRAGMA table_info(items)")}
            count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
            first_seen = conn.execute("SELECT COUNT(*) FROM items WHERE first_seen_ts IS NOT NULL").fetchone()[0] if "first_seen_ts" in columns else 0
            by_domain = dict(conn.execute("SELECT domain, COUNT(*) FROM items GROUP BY domain"))
        coverage = count / item_count if item_count else 0.
        report["corpus"] = {"path": str(paths.corpus_path), "mapped_items": item_count, "corpus_rows": count,
                            "mapping_hash": actual_mapping_hash, "coverage": coverage, "counts_by_domain": by_domain,
                            "first_seen_rows": first_seen, "declared_coverage_by_domain": meta.get("coverage_by_domain", {})}
        if not count or first_seen != count:
            report["blockers"].append("Corpus has missing first_seen timestamps; temporal coverage needs review")
        if first_seen != meta.get("num_items_with_first_seen_ts"):
            report["blockers"].append("Corpus first_seen count differs from provenance")
        if not np.isclose(coverage, meta.get("coverage", -1)) or coverage < load_config("eval/candidate_recall")["candidate_recall"]["min_metadata_coverage"]:
            report["blockers"].append("Corpus coverage differs from provenance or is below runtime minimum")
        counts = stage3.get("counts", {})
        if counts.get("num_items") != item_count:
            report["blockers"].append("Item mapping count differs from stage 3 manifest")
        for split in ("train", "validation", "test"):
            path = paths.split_path(split)
            if not path.is_file():
                report["blockers"].append(f"Missing split: {path}")
                continue
            with closing(pq.ParquetFile(path)) as parquet:
                rows = parquet.metadata.num_rows
            if counts.get(split + "_rows") != rows:
                report["blockers"].append(f"Split row count differs from manifest: {split}")
        if scan_splits:
            try:
                report["split_scan"] = _scan_splits(paths, item_count, int(counts["num_users"]), scratch_dir)
            except (ValueError, KeyError, OSError, sqlite3.Error) as exc:
                report["split_scan"] = {"status": "failed", "error": str(exc)}
                report["blockers"].append(f"Split scan failed: {exc}")
                report["status"] = "blocked"
                report["ready_for_evaluation"] = False
                return report
            report["split_scan"]["status"] = "checked"
            if report["split_scan"]["overlapping_events"] or not report["split_scan"]["temporal_order_valid"]:
                report["blockers"].append("Split temporal ordering or event-overlap check failed")
            if flags.get("data_protocol") == "temporal_train_core":
                scan = report["split_scan"]
                if scan["train"]["max_timestamp"] > flags["cutoff_1"] or scan["validation"]["min_timestamp"] <= flags["cutoff_1"] or scan["validation"]["max_timestamp"] > flags["cutoff_2"] or scan["test"]["min_timestamp"] <= flags["cutoff_2"]:
                    report["blockers"].append("Split timestamp bounds violate recorded cutoffs")
    else:
        report["blockers"].append("Missing corpus, corpus metadata or item mapping")

    if not scan_splits:
        report["blockers"].append("Split temporal/event-overlap scan not run; rerun with --scan-splits")
    for path, size, mtime in cache:
        current = Path(path).stat()
        if (current.st_size, current.st_mtime_ns) != (size, mtime):
            report["blockers"].append(f"File changed after checksum verification: {path}")
    report["blockers"] = list(dict.fromkeys(report["blockers"]))
    report["ready_for_evaluation"] = not report["blockers"]
    report["status"] = "ready_for_protocol_review" if report["ready_for_evaluation"] else "blocked"
    return report


def main():
    ensure_utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--scan-splits", action="store_true", help="Disk-backed full event and timestamp audit")
    parser.add_argument("--scratch-dir", type=Path, help="Existing directory with room for a temporary event index")
    parser.add_argument("--report", required=True, type=Path, help="New JSON report (must not exist)")
    args = parser.parse_args()
    if args.report.exists():
        parser.error("Report exists; use a new path")
    paths = resolve_bundle_paths(tag=args.tag)
    try:
        report = audit_bundle(paths, scan_splits=args.scan_splits, scratch_dir=args.scratch_dir)
    except (OSError, ValueError, KeyError, sqlite3.Error) as exc:
        report = {"tag": paths.tag, "status": "failed", "ready_for_evaluation": False, "blockers": [str(exc)]}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
    print(f"\nstatus={report['status']} report={args.report}", flush=True)
    for blocker in report.get("blockers", []):
        print(f"BLOCKED: {blocker}", flush=True)
    raise SystemExit(0 if report["ready_for_evaluation"] else 1)


if __name__ == "__main__":
    main()
