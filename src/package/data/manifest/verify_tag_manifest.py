"""Verify that a data tag has a complete, internally consistent pipeline manifest chain."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from package.config import DataPaths, get_domains
from package.config import PROJECT_ROOT
from package.tools.evaluation.sha256_file import sha256_file
from .verify_manifest import verify_manifest


def verify_tag_manifest(
    paths: DataPaths,
    *,
    domains: list[str] | None = None,
    project_root: str | Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Verify stage manifests for a tag; report legacy only when no stage manifest exists."""
    domain_list = domains or get_domains()
    stage2_manifest = paths.filtered_path.parent / "stage_2.manifest.json"
    if stage2_manifest.is_file():
        stage2_doc = json.loads(stage2_manifest.read_text(encoding="utf-8"))
        domain_list = list(stage2_doc.get("flags", {}).get("domains", domain_list))
    stage1 = [paths.stage1_manifest_path(domain) for domain in domain_list]
    expected = stage1 + [
        paths.filtered_path.parent / "stage_2.manifest.json",
        paths.splits_dir / "stage_3.manifest.json",
        paths.corpus_dir / "stage_4.manifest.json",
    ]
    present = [manifest.is_file() for manifest in expected]
    if not any(present):
        return {"status": "legacy_unmanifested", "manifest_sha256": "legacy_unmanifested", "manifests": [], "warnings": ["No pipeline manifests found for this tag; using legacy artifacts."]}
    missing = [str(p) for p, exists in zip(expected, present) if not exists]
    if missing:
        raise ValueError("Incomplete manifest chain; missing: " + ", ".join(missing))
    results = []
    records = []
    warnings: list[str] = []
    for index, manifest_path in enumerate(expected):
        result = verify_manifest(manifest_path, project_root=project_root)
        expected_stage = "clean_domain" if index < len(stage1) else ("merge_filter_domains", "map_split", "build_artifacts")[index - len(stage1)]
        if result["manifest"].get("stage") != expected_stage or result["manifest"].get("tag") != paths.tag:
            raise ValueError(f"Manifest identity mismatch at {manifest_path.name}: expected stage={expected_stage}, tag={paths.tag}")
        results.append(result)
        warnings.extend(result.get("manifest", {}).get("warnings", []))
        warnings.extend(f"external path hash cannot be independently resolved: {p}" for p in result.get("unverified_external", []))
        records.append({"path": manifest_path.resolve().relative_to(Path(project_root).resolve()).as_posix(),
                        "sha256": sha256_file(manifest_path), "status": result["status"]})
    digest = hashlib.sha256()
    for manifest_path in expected:
        relative = manifest_path.resolve().relative_to(Path(project_root).resolve()).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(manifest_path).encode("ascii"))
        digest.update(b"\0")
    return {"status": "match_with_warnings" if warnings else "match", "manifest_sha256": digest.hexdigest(), "manifests": records, "warnings": warnings}

