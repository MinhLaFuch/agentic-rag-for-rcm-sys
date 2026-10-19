"""Test stage 4: build corpus and ItemKNN artifacts."""

import tempfile
from pathlib import Path

import pytest

from package.config import DataPaths
from package.data.pipeline import build_meta_files


def test_build_meta_files(tmp_path):
    """Test build_meta_files helper function."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True)

    paths = DataPaths(
        tag="test",
        raw_dir=raw_dir,
        cleaned_dir=tmp_path / "cleaned",
        filtered_dir=tmp_path / "filtered" / "test",
        mapped_dir=tmp_path / "mapped" / "test",
        splits_dir=tmp_path / "splits" / "test",
        item_knn_dir=tmp_path / "item_knn" / "test",
        corpus_dir=tmp_path / "corpus" / "test",
        log_dir=tmp_path / "logs" / "test",
        experiments_dir=tmp_path / "experiments",
    )

    # Test with domains
    meta_files = build_meta_files(paths, ["Domain1", "Domain2"])
    assert len(meta_files) == 2
    assert meta_files[0] == ("Domain1", str(raw_dir / "meta_Domain1.jsonl.gz"))
    assert meta_files[1] == ("Domain2", str(raw_dir / "meta_Domain2.jsonl.gz"))
