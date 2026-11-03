"""
Config loader (mục XX): mọi giá trị cấu hình (dataset path, domain, model
name, top_k, batch size, LLM settings...) PHẢI đọc từ file YAML trong
configs/, không hard-code trong code.

Hỗ trợ interpolation đơn giản dạng ``${VAR_NAME}`` được thay bằng biến
môi trường tương ứng (ví dụ ``${DOMAIN}``), để domain có thể được set
qua ``DOMAIN=Video_Games python ...`` mà không cần sửa file yaml.
``${VAR_NAME:-default}`` dùng ``default`` (có thể rỗng) khi biến chưa được set —
dùng cho secret tuỳ chọn như ``api_key: ${LLM_API_KEY:-}``; secret KHÔNG được ghi vào yaml.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ._error import ConfigError
from ._constants import CONFIG_DIR
from ._helper import _interpolate_env
from ._schemas import validate_config

# Module-level cache for config file modification times
# Used to detect when config files have changed and invalidate caches
_file_mtime_cache: dict[str, float] = {}

def load_config(name: str, config_dir: Path | None = None) -> dict[str, Any]:
    """
    Load một file config theo tên (không cần đuôi .yaml), ví dụ:
        load_config("path/domains") -> đọc configs/path/domains.yaml
        load_config("eval/baselines") -> đọc configs/eval/baselines.yaml
    Ném ConfigError nếu file không tồn tại hoặc thiếu env var cần thiết.
    """
    directory = config_dir or CONFIG_DIR
    path = directory / f"{name}.yaml"
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    # Check if file has changed since last load
    current_mtime = path.stat().st_mtime
    if name in _file_mtime_cache and _file_mtime_cache[name] != current_mtime:
        # File changed, clear the LRU cache in _limits.py
        # Use public cache clearing functions to avoid cross-folder imports
        try:
            from ..agents._limits import clear_agent_limits_cache, clear_memory_limits_cache
            clear_agent_limits_cache()
            clear_memory_limits_cache()
        except ImportError:
            pass
        try:
            from ..tools._limits import clear_tool_limits_cache
            clear_tool_limits_cache()
        except ImportError:
            pass
        try:
            from ..inference._limits import clear_inference_limits_cache
            clear_inference_limits_cache()
        except ImportError:
            pass
        try:
            from ..evaluation._schema import clear_reference_plans_cache
            clear_reference_plans_cache()
        except ImportError:
            pass

    _file_mtime_cache[name] = current_mtime

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    interpolated = _interpolate_env(raw)
    validated = validate_config(name, interpolated)
    return validated
