"""Runtime limits cho ablation comparison, loaded từ configs/agent/ablation.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from package.config.loader import ConfigError, load_config


@dataclass(frozen=True)
class AblationLimits:
    bootstrap_resamples: int
    confidence: float
    min_n_warn: int
    seed: int
    metrics: list[str]
    groups: dict[str, list[str]]
    contrasts: list[dict[str, Any]]
    output_subdir: str


@lru_cache(maxsize=1)
def get_ablation_limits() -> AblationLimits:
    cfg = load_config("agent/ablation")["ablation"]
    
    bootstrap_resamples = int(cfg["bootstrap_resamples"])
    if bootstrap_resamples <= 0:
        raise ConfigError("configs/agent/ablation.yaml: bootstrap_resamples must be > 0")
    
    confidence = float(cfg["confidence"])
    if not 0 < confidence < 1:
        raise ConfigError("configs/agent/ablation.yaml: confidence must be between 0 and 1")
    
    min_n_warn = int(cfg["min_n_warn"])
    if min_n_warn <= 0:
        raise ConfigError("configs/agent/ablation.yaml: min_n_warn must be > 0")
    
    seed = int(cfg["seed"])
    
    metrics = cfg["metrics"]
    if not isinstance(metrics, list) or not metrics:
        raise ConfigError("configs/agent/ablation.yaml: metrics must be a non-empty list")
    
    groups = cfg.get("groups", {})
    if not isinstance(groups, dict):
        raise ConfigError("configs/agent/ablation.yaml: groups must be a dict")
    
    contrasts = cfg.get("contrasts", [])
    if not isinstance(contrasts, list):
        raise ConfigError("configs/agent/ablation.yaml: contrasts must be a list")
    
    output_subdir = str(cfg["output_subdir"])
    if not output_subdir:
        raise ConfigError("configs/agent/ablation.yaml: output_subdir must be non-empty")
    
    return AblationLimits(
        bootstrap_resamples=bootstrap_resamples,
        confidence=confidence,
        min_n_warn=min_n_warn,
        seed=seed,
        metrics=metrics,
        groups=groups,
        contrasts=contrasts,
        output_subdir=output_subdir,
    )
