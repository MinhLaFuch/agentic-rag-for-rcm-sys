"""Create content-addressed manifests for pipeline artifacts."""

from __future__ import annotations

import json
import hashlib
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from package.tools.recommenders.file_hash import file_hash
from package.tools.recommenders.mapping_hash import mapping_hash


def _relative(path: Path, root: Path) -> str:
    """Render a path relative to the project, including external files via `..` segments."""
    resolved, base = path.resolve(), root.resolve()
    try:
        return Path(os.path.relpath(resolved, base)).as_posix()
    except ValueError:
        # Windows cannot express relative paths across drives. Keep a stable,
        # non-reversible project-relative key instead of leaking an absolute path.
        key = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()
        return f"external/{resolved.drive.rstrip(':').lower()}/{key}/{resolved.name}"


def _git_commit(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, stderr=subprocess.DEVNULL, text=True
        ).strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        # Some Windows Python environments do not inherit Git's PATH even
        # though the checkout contains a normal .git directory. Resolve HEAD
        # directly as a read-only fallback so manifests still capture the
        # checked-out revision.
        git_root = next((candidate for candidate in (root, *root.parents)
                         if (candidate / ".git").exists()), None)
        if git_root is None:
            return "unknown"
        dot_git = git_root / ".git"
        if dot_git.is_dir():
            git_dir = dot_git.resolve()
        elif dot_git.is_file():
            marker = dot_git.read_text(encoding="utf-8").strip()
            if not marker.startswith("gitdir:"):
                return "unknown"
            git_dir = (git_root / marker.partition(":")[2].strip()).resolve()
        else:
            return "unknown"

        common_dir = git_dir
        common_marker = git_dir / "commondir"
        if common_marker.is_file():
            common_dir = (git_dir / common_marker.read_text(encoding="utf-8").strip()).resolve()

        head_path = git_dir / "HEAD"
        if not head_path.is_file():
            return "unknown"
        head = head_path.read_text(encoding="utf-8").strip()
        if len(head) in {40, 64} and all(ch in "0123456789abcdefABCDEF" for ch in head):
            return head.lower()
        if not head.startswith("ref: "):
            return "unknown"

        ref = head[5:]
        for base in dict.fromkeys((git_dir, common_dir)):
            loose_ref = base / ref
            if loose_ref.is_file():
                value = loose_ref.read_text(encoding="ascii").strip()
                if len(value) in {40, 64} and all(ch in "0123456789abcdefABCDEF" for ch in value):
                    return value.lower()
        for base in dict.fromkeys((git_dir, common_dir)):
            packed_refs = base / "packed-refs"
            if packed_refs.is_file():
                for line in packed_refs.read_text(encoding="ascii").splitlines():
                    if line and not line.startswith(("#", "^")):
                        value, _, name = line.partition(" ")
                        if name == ref and len(value) in {40, 64} and all(
                            ch in "0123456789abcdefABCDEF" for ch in value
                        ):
                            return value.lower()
        return "unknown"


def write_manifest(
    manifest_path: str | Path,
    *,
    project_root: str | Path,
    stage: str,
    tag: str,
    inputs: list[str | Path],
    outputs: list[str | Path],
    config_files: list[str | Path],
    counts: dict[str, Any],
    flags: dict[str, Any],
    upstream_manifests: list[str | Path] | None = None,
    warnings: list[str] | None = None,
    mapping_hash_overrides: dict[str | Path, str] | None = None,
) -> dict[str, Any]:
    """Hash pipeline inputs, outputs, configs and upstream manifests, then write JSON."""
    root = Path(project_root).resolve()

    # Later stages often consume the exact mapping files emitted by the
    # immediately preceding stage. Reuse that stage's mapping hash when its
    # recorded file SHA still matches, rather than parsing multi-million-entry
    # JSON mappings again just to reproduce the same value.
    upstream_mapping_hashes: dict[str, tuple[str, str]] = {}
    for upstream_path in upstream_manifests or []:
        upstream_file = Path(upstream_path)
        if not upstream_file.is_file():
            continue
        upstream_document = json.loads(upstream_file.read_text(encoding="utf-8"))
        for output in upstream_document.get("outputs", []):
            if output.get("mapping_hash") and output.get("sha256"):
                upstream_mapping_hashes[output["path"]] = (output["sha256"], output["mapping_hash"])
    mapping_hashes = {
        _relative(Path(path), root): str(digest)
        for path, digest in (mapping_hash_overrides or {}).items()
    }

    def entry(path: str | Path) -> dict[str, str]:
        resolved = Path(path).resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"Cannot manifest missing file: {_relative(resolved, root)}")
        relative = _relative(resolved, root)
        record = {"path": relative, "sha256": file_hash(resolved), "external": relative.startswith("external/")}
        if resolved.name in {"user2id.json", "item2id.json"}:
            if relative in mapping_hashes:
                record["mapping_hash"] = mapping_hashes[relative]
            else:
                upstream_mapping = upstream_mapping_hashes.get(relative)
                if upstream_mapping is not None and upstream_mapping[0] == record["sha256"]:
                    record["mapping_hash"] = upstream_mapping[1]
                else:
                    mapping = json.loads(resolved.read_text(encoding="utf-8"))
                    record["mapping_hash"] = mapping_hash(mapping)
        return record

    config_hashes = {item["path"]: item["sha256"] for item in sorted((entry(p) for p in config_files), key=lambda e: e["path"])}
    upstream = [entry(p) for p in (upstream_manifests or [])]
    document = {
        "schema_version": 1,
        "stage": stage,
        "tag": tag,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(root),
        "inputs": sorted((entry(p) for p in inputs), key=lambda e: e["path"]),
        "outputs": sorted((entry(p) for p in outputs), key=lambda e: e["path"]),
        "config_sha256": config_hashes,
        "upstream_manifests": sorted(upstream, key=lambda e: e["path"]),
        "counts": counts,
        "flags": flags,
        "warnings": warnings or [],
    }
    target = Path(manifest_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(document, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(target)
    return document

