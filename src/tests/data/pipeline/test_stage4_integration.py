"""Integration tests for stage 4 (build artifacts)."""

import tempfile
from pathlib import Path

import pytest

from package.config import DataPaths


def test_stage4_fail_fast_when_output_exists(tmp_path):
    """Stage 4 should fail fast when output exists without --force."""
    # Create minimal paths
    paths = DataPaths(
        tag="test_tag",
        raw_dir=tmp_path / "raw",
        cleaned_dir=tmp_path / "cleaned",
        filtered_dir=tmp_path / "filtered" / "test_tag",
        mapped_dir=tmp_path / "mapped" / "test_tag",
        splits_dir=tmp_path / "splits" / "test_tag",
        item_knn_dir=tmp_path / "item_knn" / "test_tag",
        corpus_dir=tmp_path / "corpus" / "test_tag",
        log_dir=tmp_path / "logs" / "test_tag",
        experiments_dir=tmp_path / "experiments",
    )

    # Create input (mapped_dir)
    paths.mapped_dir.mkdir(parents=True)
    (paths.mapped_dir / "user2id.json").write_text("{}")
    (paths.mapped_dir / "item2id.json").write_text("{}")

    # Create output (corpus file)
    paths.corpus_dir.mkdir(parents=True)
    paths.corpus_path.write_text("fake")

    # Try to build without force - should fail
    from package.data.pipeline import build_artifacts
    with pytest.raises(FileExistsError):
        build_artifacts(paths, force=False)


def test_stage4_eval_on_validation_creates_one_file(tmp_path):
    """Stage 4 with --eval-on validation should only create one ItemKNN file."""
    # This would require full splits setup - skip for now
    pytest.skip("Requires full splits setup")


def test_stage4_skip_corpus_skips_corpus_building(tmp_path):
    """Stage 4 with --skip-corpus should skip corpus building."""
    # Create minimal paths
    paths = DataPaths(
        tag="test_tag",
        raw_dir=tmp_path / "raw",
        cleaned_dir=tmp_path / "cleaned",
        filtered_dir=tmp_path / "filtered" / "test_tag",
        mapped_dir=tmp_path / "mapped" / "test_tag",
        splits_dir=tmp_path / "splits" / "test_tag",
        item_knn_dir=tmp_path / "item_knn" / "test_tag",
        corpus_dir=tmp_path / "corpus" / "test_tag",
        log_dir=tmp_path / "logs" / "test_tag",
        experiments_dir=tmp_path / "experiments",
    )

    # Create input (mapped_dir)
    paths.mapped_dir.mkdir(parents=True)
    (paths.mapped_dir / "user2id.json").write_text("{}")
    (paths.mapped_dir / "item2id.json").write_text("{}")

    # Create raw/meta
    paths.raw_dir.mkdir(parents=True)
    (paths.raw_dir / "meta_Domain.jsonl.gz").write_text("fake")

    # Build with skip_corpus - should not create corpus file
    from package.data.pipeline import build_artifacts
    report = build_artifacts(paths, skip_corpus=True, skip_item_knn=True, force=True, allow_manifest_mismatch=True)

    assert "corpus" in report
    assert report["corpus"] == {}  # Empty because skipped
    assert not paths.corpus_path.exists()


def test_stage4_skip_item_knn_skips_item_knn_building(tmp_path):
    """Stage 4 with --skip-item-knn should skip ItemKNN building."""
    # Similar to skip_corpus test
    pytest.skip("Requires full splits setup")


def test_datapaths_corpus_path_and_item_knn_path(tmp_path):
    """Test DataPaths corpus_path and item_knn_path methods."""
    paths = DataPaths(
        tag="test_tag",
        raw_dir=tmp_path / "raw",
        cleaned_dir=tmp_path / "cleaned",
        filtered_dir=tmp_path / "filtered" / "test_tag",
        mapped_dir=tmp_path / "mapped" / "test_tag",
        splits_dir=tmp_path / "splits" / "test_tag",
        item_knn_dir=tmp_path / "item_knn" / "test_tag",
        corpus_dir=tmp_path / "corpus" / "test_tag",
        log_dir=tmp_path / "logs" / "test_tag",
        experiments_dir=tmp_path / "experiments",
    )

    # Test corpus_path
    assert paths.corpus_path == paths.corpus_dir / "corpus_test_tag.sqlite"

    # Test item_knn_path
    assert paths.item_knn_path("validation") == paths.item_knn_dir / "item_knn_test_tag_validation.npz"
    assert paths.item_knn_path("test") == paths.item_knn_dir / "item_knn_test_tag_test.npz"
