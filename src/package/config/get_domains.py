from __future__ import annotations

from typing import Any

from .load_config import load_config


def get_domains(config: dict[str, Any] | None = None) -> list[str]:
    config = config or load_config("path/domains")
    return [d["name"] for d in config["domains"]]
