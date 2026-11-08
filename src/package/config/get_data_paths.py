from __future__ import annotations

from pathlib import Path
from typing import Any

from ._constants import PROJECT_ROOT
from ._dataclass import DataPaths
from .get_domains import resolve_dataset_tag
from .load_config import load_config


def get_data_paths(
    tag: str | None = None,
    config: dict[str, Any] | None = None,
    domains: list[str] | None = None,
) -> DataPaths:
    """Resolve data paths for a dataset bundle.

    ``tag`` is a low-level override kept for tests and for reading artifacts
    of old experiments (whose manifests store a historical tag such as
    ``"default"``). Production callers should pass ``domains`` instead — the
    tag is then derived by :func:`resolve_dataset_tag` (one domain -> its
    name, all/none -> ``merged_name``). With neither, the merged dataset is
    used.
    """
    if config is None:
        paths = load_config("path/data_paths")["paths"]
    else:
        paths = config["paths"]
        tag = tag or config.get("tag")

    if tag is None:
        tag = resolve_dataset_tag(domains)

    def root(key: str) -> Path:
        return PROJECT_ROOT / paths[key]

    def artifact_dir(key: str, filename: str) -> Path:
        """Resolve tagged artifacts, while accepting the earlier flat layout."""
        tagged = root(key) / tag
        if (tagged / filename).exists():
            return tagged
        flat = root(key)
        if (flat / filename).exists():
            return flat
        return tagged

    return DataPaths(
        tag=tag,
        src_root=root("src_root"),
        config_dir=root("config_dir"),
        raw_dir=root("raw_dir"),
        cleaned_dir=root("cleaned_dir"),
        filtered_dir=root("filtered_dir") / tag,
        mapped_dir=root("mapped_dir") / tag,
        splits_dir=root("splits_dir") / tag,
        item_knn_dir=artifact_dir("item_knn_dir", f"item_knn_{tag}_validation.npz"),
        corpus_dir=artifact_dir("corpus_dir", f"corpus_{tag}.sqlite"),
        log_dir=root("log_dir") / tag,
        experiments_dir=root("experiments_dir"),
    )
