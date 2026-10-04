"""Dataclass definitions for config module."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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
