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

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    return _interpolate_env(raw)
