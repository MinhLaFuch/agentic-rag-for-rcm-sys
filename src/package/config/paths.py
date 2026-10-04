"""
Đường dẫn dữ liệu của pipeline, đọc từ ``configs/data.yaml``.

Layout (gốc là ``resource/``, đổi trong data.yaml → paths):

    resource/raw/<Domain>.jsonl.gz            review thô (tải về tay / download_review_data.sh)
    resource/raw/meta_<Domain>.jsonl.gz       metadata item thô
    resource/cleaned/<Domain>/interactions.parquet           stage 1
    resource/filtered/<tag>/interactions.parquet             stage 2
    resource/mapped/<tag>/{user2id,item2id}.json             stage 3
    resource/splits/<tag>/{train,validation,test}.parquet    stage 3

``tag`` là tên một lần chạy (mặc định ``run_tag`` trong data.yaml), để thử
2 domain mà không ghi đè bản chạy đủ.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._config import PROJECT_ROOT
from .loader import load_config


@dataclass(frozen=True)
class DataPaths:
    tag: str
    raw_dir: Path
    cleaned_dir: Path
    filtered_dir: Path
    mapped_dir: Path
    splits_dir: Path

    def review_path(self, domain: str) -> Path:
        return self.raw_dir / f"{domain}.jsonl.gz"

    def meta_path(self, domain: str) -> Path:
        return self.raw_dir / f"meta_{domain}.jsonl.gz"

    def cleaned_path(self, domain: str) -> Path:
        return self.cleaned_dir / domain / "interactions.parquet"

    @property
    def filtered_path(self) -> Path:
        return self.filtered_dir / "interactions.parquet"


def get_domains(config: dict[str, Any] | None = None) -> list[str]:
    """Tên các domain bật trong data.yaml (giữ thứ tự khai báo)."""
    config = config or load_config("data")
    return [d["name"] for d in config["domains"]]


def get_data_paths(tag: str | None = None, config: dict[str, Any] | None = None) -> DataPaths:
    config = config or load_config("data")
    tag = tag or config["run_tag"]
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
    )
