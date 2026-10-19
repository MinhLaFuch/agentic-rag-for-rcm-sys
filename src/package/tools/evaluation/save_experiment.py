from __future__ import annotations

import json
import hashlib
import importlib.metadata
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from ._helper import _git_commit
from .hardware_info import hardware_info


def _source_fingerprint() -> str:
    """Hash implementation/config sources so runs remain identifiable without Git."""
    project_root = Path(__file__).resolve().parents[3]
    files = [project_root / "pyproject.toml"]
    for folder in ("package", "scripts", "configs"):
        base = project_root / folder
        if base.exists():
            files.extend(path for path in base.rglob("*") if path.suffix in {".py", ".yaml", ".yml"})
    digest = hashlib.sha256()
    for path in sorted(set(files)):
        if not path.is_file():
            continue
        digest.update(path.relative_to(project_root).as_posix().encode("utf-8"))
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
) -> Path:
    """Save experiment results to directory with config, metrics, and README."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=False)

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
    with open(out / "README.md", "w", encoding="utf-8") as f:
        f.write(f"# {out.name}\n\n")
        f.write(f"- timestamp: {record['timestamp']}\n- seed: {seed}\n")
        f.write(f"- git_commit: {record['git_commit']}\n- runtime_seconds: {record['runtime_seconds']}\n")
        f.write(f"- dataset: {json.dumps(dataset_info)}\n")
        if notes:
            f.write(f"\n{notes}\n")
    return out
