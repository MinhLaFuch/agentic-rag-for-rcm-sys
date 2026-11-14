from __future__ import annotations

import json
import hashlib
import importlib.metadata
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from ..core._helper import _git_commit
from ..utils.hardware_info import hardware_info


def _source_fingerprint() -> str:
    """Hash implementation/config sources so runs remain identifiable without Git.

    Root is src/ (parents[4]): parents[5] is the repo root where package/,
    scripts/ and configs/ do NOT exist — the old code silently hashed only
    pyproject.toml, so code drift was invisible to resume/provenance.
    """
    src_root = Path(__file__).resolve().parents[4]
    repo_root = src_root.parent
    files = [repo_root / "pyproject.toml"]
    for folder in ("package", "scripts", "configs"):
        base = src_root / folder
        if base.exists():
            files.extend(
                path
                for path in base.rglob("*")
                if path.suffix in {".py", ".yaml", ".yml"}
                and "__pycache__" not in path.parts
                and path.suffix != ".pyc"
            )
    digest = hashlib.sha256()
    for path in sorted(set(files)):
        if not path.is_file():
            continue
        digest.update(path.relative_to(repo_root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _environment_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for distribution in ("numpy", "pandas", "scipy", "pyarrow", "PyYAML", "pytest", "torch"):
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = None
    versions["python"] = sys.version.split()[0]
    return versions


def save_experiment(
    output_dir: str | Path,
    *,
    config: dict[str, Any],
    metrics: dict[str, Any],
    seed: int,
    dataset_info: dict[str, Any],
    runtime_seconds: float,
    notes: str = "",
    write_readme: bool = True,
    exist_ok: bool = False,
) -> Path:
    """Save experiment results to directory with config, metrics, and README.

    ``exist_ok=True`` is for callers that legitimately pre-create the dir —
    run_agent_eval does this when the multi-turn step writes
    ``multi_turn.json`` into the experiment dir before save_experiment runs.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=exist_ok)

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "git_commit": _git_commit(),
        "source_fingerprint": _source_fingerprint(),
        "environment": _environment_versions(),
        "hardware": hardware_info(),
        "runtime_seconds": round(runtime_seconds, 2),
        "dataset": dataset_info,
    }

    with open(out / "config.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump({"run": record, "config": config}, f, sort_keys=False, allow_unicode=True)
    with open(out / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    if not write_readme:
        return out
    with open(out / "README.md", "w", encoding="utf-8") as f:
        f.write(f"# {out.name}\n\n")
        f.write(f"- timestamp: {record['timestamp']}\n- seed: {seed}\n")
        f.write(f"- git_commit: {record['git_commit']}\n- runtime_seconds: {record['runtime_seconds']}\n")
        f.write(f"- dataset: {json.dumps(dataset_info)}\n")
        if notes:
            f.write(f"\n{notes}\n")
    return out
