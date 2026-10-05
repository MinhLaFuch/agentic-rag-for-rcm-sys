from __future__ import annotations

from pathlib import Path
from typing import Any

from ._constants import PROJECT_ROOT
from ._dataclass import DataPaths
from .loader import load_config


def get_data_paths(tag: str | None = None, config: dict[str, Any] | None = None) -> DataPaths:
    if config is None:
        tag_config = load_config("run_tag")
        tag = tag or tag_config["tag"]
        paths_config = load_config("data_paths")
        paths = paths_config["paths"]
    else:
        tag = tag or config["tag"]
        paths = config["paths"]

    def root(key: str) -> Path:
        return PROJECT_ROOT / paths[key]

    return DataPaths(
        tag=tag,
        raw_dir=root("raw_dir"),
        cleaned_dir=root("cleaned_dir"),
        filtered_dir=root("filtered_dir") / tag,
        mapped_dir=root("mapped_dir") / tag,
        splits_dir=root("splits_dir") / tag,
        log_dir=root("log_dir") / tag,
        experiments_dir=root("experiments_dir"),
    )
