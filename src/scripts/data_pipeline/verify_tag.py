"""Read-only verification report for a data tag's pipeline manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from package.config import get_data_paths, get_domains
from package.data.manifest import verify_tag_manifest
from package.config import PROJECT_ROOT
from package.tools.evaluation.sha256_file import sha256_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    paths = get_data_paths(args.tag)
    stage2 = paths.filtered_path.parent / "stage_2.manifest.json"
    domains = get_domains()
    if stage2.is_file():
        domains = json.loads(stage2.read_text(encoding="utf-8")).get("flags", {}).get("domains", domains)
    manifest_paths = [paths.stage1_manifest_path(domain) for domain in domains]
    manifest_paths += [stage2, paths.splits_dir / "stage_3.manifest.json", paths.corpus_dir / "stage_4.manifest.json"]
    try:
        result = verify_tag_manifest(paths, domains=domains)
    except (FileNotFoundError, ValueError) as exc:
        print(f"tag={args.tag} status=MISMATCH")
        print(str(exc))
        failed = True
        result = {"status": "mismatch", "manifest_sha256": "unavailable", "warnings": []}
    else:
        failed = False
    print(f"tag={args.tag} status={result['status']} manifest_sha256={result['manifest_sha256']}")
    if result["status"] == "legacy_unmanifested":
        print("WARNING: no manifests found; this tag contains legacy/unverified artifacts.")
        return
    print(f"{'PATH':70} {'EXPECTED SHA256':64} {'ACTUAL SHA256':64} STATUS")
    for manifest_path in manifest_paths:
        if not manifest_path.is_file():
            label = str(manifest_path.relative_to(PROJECT_ROOT)) if manifest_path.is_relative_to(PROJECT_ROOT) else manifest_path.name
            print(f"{label:70} {'-':64} {'-':64} MISSING")
            continue
        doc = json.loads(manifest_path.read_text(encoding="utf-8"))
        artifacts = doc.get("inputs", []) + doc.get("outputs", []) + doc.get("upstream_manifests", []) + [
            {"path": p, "sha256": h} for p, h in doc.get("config_sha256", {}).items()
        ]
        for artifact in artifacts:
            rel, expected = artifact["path"], artifact["sha256"]
            if artifact.get("external"):
                actual, state = "-", "EXTERNAL_RECORDED"
            else:
                target = (PROJECT_ROOT / rel).resolve()
                actual = sha256_file(target) if target.is_file() else "missing"
                state = "MATCH" if actual == expected else "MISMATCH"
            print(f"{rel:70} {expected:64} {actual:64} {state}")
    for warning in result.get("warnings", []):
        print(f"WARNING: {warning}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
