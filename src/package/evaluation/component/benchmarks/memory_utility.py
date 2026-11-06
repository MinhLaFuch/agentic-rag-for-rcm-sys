"""Memory Utility analysis module.

Provides the public API for paired, multi-run comparison of planner vs planner_memory.
This module re-exports functions from submodules for backward compatibility with tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .analyze_metric import analyze_metric
from .scope_of import scope_of
from .analyze import analyze
from .default_metrics import default_metrics
from .render_markdown import render_markdown
from package.config import load_config
from package.evaluation.ablation import check_compatibility, load_config_data, load_scored_data


def _load_runs(dirs: list[str]) -> tuple[list[list[dict]], list[dict]]:
    scored, cfgs = [], []
    for d in dirs:
        p = Path(d)
        scored.append(load_scored_data(p))
        try:
            cfgs.append(load_config_data(p))
        except Exception:  # config optional for analysis; compatibility check is skipped
            pass
    return scored, cfgs


def memory_utility(argv: list[str] | None = None) -> int:
    """CLI entry point for memory utility analysis.

    Mọi tham số (kể cả input dirs và metrics) đọc từ configs/eval/memory_utility.yaml;
    dirs là đường dẫn tương đối so với experiments_dir.
    """
    if argv:
        raise SystemExit("memory_utility takes no arguments; set dirs/metrics in configs/eval/memory_utility.yaml")

    # Mọi tham số phân tích đọc từ configs/eval/memory_utility.yaml; output từ data_paths.outputs.memory_utility
    cfg = load_config("eval/memory_utility")["memory_utility"]
    k = int(cfg["k"])
    resamples = int(cfg["resamples"])
    confidence = float(cfg["confidence"])
    min_n = int(cfg["min_n"])
    seed = int(cfg["seed"])
    baseline_agent = str(cfg["baseline_agent"])
    memory_agent = str(cfg["memory_agent"])

    from package.config import get_data_paths
    exp_root = get_data_paths().experiments_dir

    def _resolve(dirs: list[str]) -> list[str]:
        return [str(exp_root / d) if not Path(d).is_absolute() else d for d in dirs]

    a_dirs = _resolve(list(cfg.get("baseline_dirs") or [])) or _resolve(list(cfg.get("dirs") or []))
    b_dirs = _resolve(list(cfg.get("memory_dirs") or [])) or _resolve(list(cfg.get("dirs") or []))
    if not a_dirs or not b_dirs:
        raise SystemExit("memory_utility.dirs or baseline_dirs+memory_dirs must list experiment dirs in configs/eval/memory_utility.yaml")
    runs_a, cfg_a = _load_runs(a_dirs)
    runs_b, cfg_b = _load_runs(b_dirs)

    compat: list[str] = []
    ref = (cfg_a or cfg_b or [None])[0]
    if ref is not None:
        for i, c in enumerate(cfg_a + cfg_b):
            ok, why = check_compatibility(ref, c)
            if not ok:
                compat.append(f"run #{i} incompatible with first run: {why}")

    metrics = list(cfg.get("metrics") or []) or default_metrics(k)
    kw = dict(resamples=resamples, confidence=confidence, seed=seed, min_n=min_n)
    result = analyze(runs_a, runs_b, baseline_agent, memory_agent, metrics, **kw)
    meta = {"agent_a": baseline_agent, "agent_b": memory_agent, "runs_a": len(runs_a),
            "runs_b": len(runs_b), "compat_warnings": compat, "dirs_a": a_dirs, "dirs_b": b_dirs, **kw}

    from package.config import get_data_paths
    out = get_data_paths().output_dir("memory_utility")
    out.mkdir(parents=True, exist_ok=True)
    (out / "memory_utility.json").write_text(json.dumps({"meta": meta, "result": result}, indent=2), encoding="utf-8")
    md = render_markdown(result, meta)
    (out / "memory_utility.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


# Backward compatibility
main = memory_utility


__all__ = ["analyze_metric", "main", "scope_of"]