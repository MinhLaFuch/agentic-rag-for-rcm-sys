from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from ._helper import _git_commit
from .hardware_info import hardware_info


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
