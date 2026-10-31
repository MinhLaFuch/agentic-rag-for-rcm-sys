"""Verify recorded artifact hashes in a pipeline manifest."""

from __future__ import annotations

import json
from pathlib import Path
from pathlib import PureWindowsPath
from typing import Any

from package.tools.evaluation.sha256_file import sha256_file


def verify_manifest(
    manifest_path: str | Path,
    *,
    project_root: str | Path,
    allow_mismatch: bool = False,
) -> dict[str, Any]:
    """Validate every input, output, config and upstream-manifest hash in one manifest."""
    root = Path(project_root).resolve()
    path = Path(manifest_path)
    if not path.is_file():
        raise FileNotFoundError(f"Manifest missing: {path}")
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != 1:
        raise ValueError(f"Unsupported manifest schema in {path.name}: {document.get('schema_version')!r}")
    mismatches: list[str] = []
    unverified_external: list[str] = []
    recorded_files = document.get("inputs", []) + document.get("outputs", [])
    recorded_files += [{"path": name, "sha256": digest} for name, digest in document.get("config_sha256", {}).items()]
    recorded_files += document.get("upstream_manifests", [])
    for record in recorded_files:
        relative = record["path"]
        if Path(relative).is_absolute() or PureWindowsPath(relative).is_absolute():
            raise ValueError(f"Manifest contains an absolute path: {relative}")
        if record.get("external"):
            unverified_external.append(relative)
            continue
        artifact = (root / relative).resolve()
        expected = record["sha256"]
        actual = sha256_file(artifact) if artifact.is_file() else "missing"
        if actual != expected:
            mismatches.append(f"{relative}: expected={expected} actual={actual}")
    status = "mismatch" if mismatches else ("match_with_external_paths" if unverified_external else "match")
    result = {"status": status, "manifest": document, "mismatches": mismatches, "unverified_external": unverified_external}
    if mismatches and not allow_mismatch:
        raise ValueError("Manifest hash mismatch:\n" + "\n".join(mismatches))
    return result

