"""
Config loader (mục XX): mọi giá trị cấu hình (dataset path, domain, model
name, top_k, batch size, LLM settings...) PHẢI đọc từ file YAML trong
configs/, không hard-code trong code.

Hỗ trợ interpolation đơn giản dạng ``${VAR_NAME}`` được thay bằng biến
môi trường tương ứng (ví dụ ``${DOMAIN}``), để domain có thể được set
qua ``DOMAIN=Video_Games python ...`` mà không cần sửa file yaml.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"


class ConfigError(RuntimeError):
    pass


def _interpolate_env(value: Any) -> Any:
    if isinstance(value, str):
        def _replace(match: re.Match) -> str:
            var_name = match.group(1)
            if var_name not in os.environ:
                raise ConfigError(
                    f"Config references ${{{var_name}}} but env var "
                    f"'{var_name}' is not set."
                )
            return os.environ[var_name]

        return _ENV_VAR_PATTERN.sub(_replace, value)
    if isinstance(value, dict):
        return {k: _interpolate_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_env(v) for v in value]
    return value


def load_config(name: str, config_dir: Path | None = None) -> dict[str, Any]:
    """
    Load một file config theo tên (không cần đuôi .yaml), ví dụ:
        load_config("data") -> đọc configs/data.yaml
    Ném ConfigError nếu file không tồn tại hoặc thiếu env var cần thiết.
    """
    directory = config_dir or CONFIG_DIR
    path = directory / f"{name}.yaml"
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    return _interpolate_env(raw)
