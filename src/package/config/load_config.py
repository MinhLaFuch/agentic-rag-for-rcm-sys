"""
Config loader (mục XX): mọi giá trị cấu hình (dataset path, domain, model
name, top_k, batch size, LLM settings...) PHẢI đọc từ file YAML trong
configs/, không hard-code trong code.

Hỗ trợ interpolation đơn giản dạng ``${VAR_NAME}`` được thay bằng biến
môi trường tương ứng (ví dụ ``${DOMAIN}``), để domain có thể được set
qua ``DOMAIN=Video_Games python ...`` mà không cần sửa file yaml.
``${VAR_NAME:-default}`` dùng ``default`` (có thể rỗng) khi biến chưa được set —
dùng cho secret tuỳ chọn như ``api_key: ${LLM_API_KEY:-}``; secret KHÔNG được ghi vào yaml.

Overlay: biến môi trường ``CONFIG_OVERLAY_PATH`` trỏ tới một file YAML cùng dạng
configs/ (top-level key là tên config, vd ``agent/agent_eval``) được merge đè lên
config gốc trước khi validate — dùng cho per-run overrides (campaign runner, tests).
Không set biến này thì hành vi y hệt cũ.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ._error import ConfigError
from ._constants import CONFIG_DIR
from ._helper import _interpolate_env, _deep_merge, _overlay_fragment, _overlay_signature, _check_overlay_keys
from ._schemas import validate_config

# Module-level cache for config file modification times
# Used to detect when config files have changed and invalidate caches
_file_mtime_cache: dict[str, tuple] = {}
_last_overlay_signature: tuple | None = None
_overlay_notice_shown = False


def _clear_limit_caches() -> None:
    """Drop the lru caches that wrap load_config so edited YAML takes effect."""
    try:
        from ..agents import clear_agent_limits_cache, clear_memory_limits_cache
        clear_agent_limits_cache()
        clear_memory_limits_cache()
    except ImportError:
        pass
    try:
        from ..tools import clear_tool_limits_cache
        clear_tool_limits_cache()
    except ImportError:
        pass
    try:
        from ..inference import clear_inference_limits_cache
        clear_inference_limits_cache()
    except ImportError:
        pass
    try:
        from ..evaluation import clear_reference_plans_cache
        clear_reference_plans_cache()
    except ImportError:
        pass


def load_config(name: str, config_dir: Path | None = None) -> dict[str, Any]:
    """
    Load một file config theo tên (không cần đuôi .yaml), ví dụ:
        load_config("path/domains") -> đọc configs/path/domains.yaml
        load_config("eval/baselines") -> đọc configs/eval/baselines.yaml
    Ném ConfigError nếu file không tồn tại hoặc thiếu env var cần thiết.
    """
    global _last_overlay_signature
    directory = config_dir or CONFIG_DIR
    path = directory / f"{name}.yaml"
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    # An overlay change affects every config, not just one file: clear caches once per change.
    overlay_signature = _overlay_signature()
    if overlay_signature != _last_overlay_signature:
        _last_overlay_signature = overlay_signature
        _clear_limit_caches()

    # Check if file has changed since last load
    stat = path.stat()
    file_signature = (stat.st_mtime_ns, stat.st_size)
    if name in _file_mtime_cache and _file_mtime_cache[name] != file_signature:
        _clear_limit_caches()

    _file_mtime_cache[name] = file_signature

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    overlay, overlay_path = _overlay_fragment(name)
    global _overlay_notice_shown
    if overlay_path is not None and not _overlay_notice_shown:
        _overlay_notice_shown = True
        print(f"[config] CONFIG_OVERLAY_PATH active: {overlay_path}")
    if overlay:
        _check_overlay_keys(name, overlay, raw, overlay_path)
        raw = _deep_merge(raw, overlay)

    interpolated = _interpolate_env(raw)
    validated = validate_config(name, interpolated)
    return validated
