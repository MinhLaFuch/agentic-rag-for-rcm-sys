from __future__ import annotations

from pathlib import Path


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
