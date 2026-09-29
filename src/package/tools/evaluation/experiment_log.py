from __future__ import annotations

import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def _git_commit() -> str | None:
    """Get current git commit hash if available."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5
        )
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def hardware_info() -> dict[str, Any]:
    """Get hardware and platform information."""
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
    }


def next_experiment_dir(root: str | Path = "experiments") -> Path:
    """Generate the next experiment directory name."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    existing = [
        int(p.name.split("_")[1])
        for p in root.glob("exp_*")
        if p.is_dir() and p.name.split("_")[1].isdigit()
    ]
    return root / f"exp_{(max(existing) + 1 if existing else 1):03d}"


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
    out.mkdir(parents=True, exist_ok=False)  # không ghi đè experiment cũ

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "git_commit": _git_commit(),
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
