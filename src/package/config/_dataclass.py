"""Dataclass definitions for config module."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

INTERACTIONS_FILE = "interactions.parquet"  # stage 1 (per domain) and stage 2 (per run tag) output name


@dataclass(frozen=True)
class DataPaths:
    """Every project directory, resolved from configs/path/data_paths.yaml (+ run tag). The one source of truth."""

    tag: str
    raw_dir: Path
    cleaned_dir: Path
    filtered_dir: Path
    mapped_dir: Path
    splits_dir: Path
    item_knn_dir: Path  # cached ItemKNN similarity matrices: resource/item_knn/<tag>/
    corpus_dir: Path  # cached ItemCorpus databases: resource/corpus/<tag>/
    log_dir: Path  # pipeline/tool logs: experiments/logs/<tag>/ (NOT experiment results, NOT test logs)
    experiments_dir: Path  # experiment artifacts: experiments/exp_NNN/

    @property
    def corpus_path(self) -> Path:
        return self.corpus_dir / f"corpus_{self.tag}.sqlite"

    def item_knn_path(self, eval_on: str) -> Path:
        return self.item_knn_dir / f"item_knn_{self.tag}_{eval_on}.npz"

    def review_path(self, domain: str) -> Path:
        return self.raw_dir / f"{domain}.jsonl.gz"

    def meta_path(self, domain: str) -> Path:
        # Product metadata can live separately from review dumps and may be
        # plain JSONL. Prefer it when present; retain the legacy raw layout.
        metadata_path = self.raw_dir.parent / "metadata" / f"meta_{domain}.jsonl"
        if metadata_path.exists():
            return metadata_path
        plain_raw_path = self.raw_dir / f"meta_{domain}.jsonl"
        if plain_raw_path.exists():
            return plain_raw_path
        return self.raw_dir / f"meta_{domain}.jsonl.gz"

    def cleaned_path(self, domain: str) -> Path:
        return self.cleaned_dir / domain / INTERACTIONS_FILE

    @property
    def filtered_path(self) -> Path:
        return self.filtered_dir / INTERACTIONS_FILE

    def split_path(self, name: str) -> Path:
        """File of one split ("train" | "validation" | "test"); naming is owned by package.data.split."""
        from ..data.split import split_path  # lazy: keep config import-light and cycle-free

        return split_path(self.splits_dir, name)
