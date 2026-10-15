"""Load và validate dữ liệu từ các experiment directories."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from package.config import get_data_paths
from package.config.loader import ConfigError
from ._limits import get_ablation_limits


def load_scored_data(exp_dir: Path) -> list[dict[str, Any]]:
    """Load scored.jsonl từ một experiment directory."""
    scored_path = exp_dir / "scored.jsonl"
    if not scored_path.exists():
        raise ConfigError(f"scored.jsonl not found in {exp_dir}")
    
    data = []
    with scored_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def load_config_data(exp_dir: Path) -> dict[str, Any]:
    """Load config.yaml từ một experiment directory."""
    config_path = exp_dir / "config.yaml"
    if not config_path.exists():
        raise ConfigError(f"config.yaml not found in {exp_dir}")
    
    with config_path.open("r", encoding="utf-8") as f:
        import yaml
        return yaml.safe_load(f)


def load_group_data(group_name: str, exp_names: list[str]) -> dict[str, Any]:
    """
    Load dữ liệu từ một group (nhiều exp directories).
    
    Trả về dict với:
    - configs: list[dict] - config của từng exp
    - scored: list[list[dict]] - scored data của từng exp
    - exp_dirs: list[Path] - đường dẫn các exp directories
    """
    data_paths = get_data_paths()
    base_dir = data_paths.experiments_dir / "agent_eval"
    
    configs = []
    scored_list = []
    exp_dirs = []
    
    for exp_name in exp_names:
        exp_dir = base_dir / exp_name
        if not exp_dir.exists():
            raise ConfigError(f"Experiment directory not found: {exp_dir}")
        
        configs.append(load_config_data(exp_dir))
        scored_list.append(load_scored_data(exp_dir))
        exp_dirs.append(exp_dir)
    
    return {
        "group_name": group_name,
        "configs": configs,
        "scored": scored_list,
        "exp_dirs": exp_dirs,
    }


def validate_contrast_config(contrast: dict[str, Any], groups: dict[str, list[str]]) -> None:
    """Validate cấu hình contrast."""
    if "name" not in contrast:
        raise ConfigError("Contrast must have 'name'")
    if "a" not in contrast or "b" not in contrast:
        raise ConfigError("Contrast must have 'a' and 'b'")
    
    a_agent, a_group = contrast["a"]
    b_agent, b_group = contrast["b"]
    
    if a_group not in groups:
        raise ConfigError(f"Group '{a_group}' not found in groups")
    if b_group not in groups:
        raise ConfigError(f"Group '{b_group}' not found in groups")


def check_compatibility(
    config_a: dict[str, Any],
    config_b: dict[str, Any],
) -> tuple[bool, str]:
    """
    Kiểm tra tính tương thích giữa hai config.
    
    Điều kiện để so:
    - seed khớp
    - per_segment khớp
    - eval_on khớp
    - language khớp
    - k khớp
    
    Trả về (compatible, reason)
    """
    cfg_a = config_a.get("config", {})
    cfg_b = config_b.get("config", {})
    
    if cfg_a.get("seed") != cfg_b.get("seed"):
        return False, f"seed mismatch: {cfg_a.get('seed')} vs {cfg_b.get('seed')}"
    
    if cfg_a.get("per_segment") != cfg_b.get("per_segment"):
        return False, f"per_segment mismatch: {cfg_a.get('per_segment')} vs {cfg_b.get('per_segment')}"
    
    dataset_a = config_a.get("dataset", {})
    dataset_b = config_b.get("dataset", {})
    
    if dataset_a.get("eval_on") != dataset_b.get("eval_on"):
        return False, f"eval_on mismatch: {dataset_a.get('eval_on')} vs {dataset_b.get('eval_on')}"
    
    if cfg_a.get("language") != cfg_b.get("language"):
        return False, f"language mismatch: {cfg_a.get('language')} vs {cfg_b.get('language')}"
    
    if cfg_a.get("k") != cfg_b.get("k"):
        return False, f"k mismatch: {cfg_a.get('k')} vs {cfg_b.get('k')}"
    
    return True, ""
