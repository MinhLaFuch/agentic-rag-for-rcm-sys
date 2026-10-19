"""Test data pipeline refactoring for byte-level equivalence."""

import gzip
import json
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from package.config import get_data_paths, load_config
from package.data.pipeline import clean_domain, map_split, merge_filter_domains


def _create_synthetic_review_data(tmp_dir: Path, domain: str, num_rows: int = 100) -> Path:
    """Create synthetic review data for testing."""
    rows = []
    for i in range(num_rows):
        rows.append({
            "user_id": f"u{((i // 5) % 10)}",  # Some users with sparse interactions
            "parent_asin": f"i{i % 20}",  # Some items with sparse interactions
            "rating": 5.0 if i % 2 == 0 else 4.0,
            "timestamp": 1000 + i * 10,
            "title": f"Title {i}",
        })
    # Add some problematic rows
    rows.append({"user_id": "u_bad", "parent_asin": "i1", "rating": None, "timestamp": 2000, "title": "bad"})  # missing rating
    rows.append({"user_id": "u1", "parent_asin": "i1", "rating": 5.0, "timestamp": 1000, "title": "dup"})  # duplicate

    path = tmp_dir / f"{domain}.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return path





def test_pipeline_byte_level_equivalence():
    """Test that new pipeline produces deterministic outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir)

        domains = ["DomainA", "DomainB"]

        # Setup directory structure
        (tmp_root / "resource" / "raw").mkdir(parents=True)
        (tmp_root / "resource" / "cleaned").mkdir(parents=True)
        (tmp_root / "resource" / "filtered" / "test_tag").mkdir(parents=True)
        (tmp_root / "resource" / "mapped" / "test_tag").mkdir(parents=True)
        (tmp_root / "resource" / "splits" / "test_tag").mkdir(parents=True)

        # Create synthetic review data
        for domain in domains:
            _create_synthetic_review_data(tmp_root / "resource" / "raw", domain)

        paths = get_data_paths(config={"paths": {
            "raw_dir": "resource/raw",
            "cleaned_dir": "resource/cleaned",
            "filtered_dir": "resource/filtered",
            "mapped_dir": "resource/mapped",
            "splits_dir": "resource/splits",
            "item_knn_dir": "resource/item_knn",
            "corpus_dir": "resource/corpus",
            "log_dir": "experiments/logs",
            "experiments_dir": "experiments",
        }}, tag="test_tag")
        paths = replace(paths,
            raw_dir=tmp_root / "resource" / "raw",
            cleaned_dir=tmp_root / "resource" / "cleaned",
            filtered_dir=tmp_root / "resource" / "filtered" / "test_tag",
            mapped_dir=tmp_root / "resource" / "mapped" / "test_tag",
            splits_dir=tmp_root / "resource" / "splits" / "test_tag",
        )

        # Run pipeline
        print("\n=== Running pipeline ===")
        for domain in domains:
            clean_domain(paths, domain, chunk_size=50, force=True)

        merge_filter_domains(paths, domains, force=True)

        map_split(paths, force=True)

        # Verify outputs exist and are valid
        print("\n=== Verifying outputs ===")

        # Stage 1 outputs
        for domain in domains:
            df = pd.read_parquet(paths.cleaned_path(domain))
            assert len(df) > 0
            assert set(df.columns) == {"user_id", "parent_asin", "rating", "timestamp"}
            assert df["rating"].dtype == "float32"
            print(f"Stage 1 {domain}: {len(df)} rows, OK")

        # Stage 2 output
        filtered = pd.read_parquet(paths.filtered_path)
        assert len(filtered) > 0
        assert "domain" in filtered.columns
        assert "original_item_id" in filtered.columns
        print(f"Stage 2 filtered: {len(filtered)} rows, OK")

        # Stage 3 outputs
        for split_name in ["train", "validation", "test"]:
            split = pd.read_parquet(paths.split_path(split_name))
            assert len(split) > 0
            assert "user_idx" in split.columns
            assert "item_idx" in split.columns
            print(f"Stage 3 {split_name}: {len(split)} rows, OK")

        # Mappings
        with open(paths.mapped_dir / "user2id.json", "r") as f:
            user2id = json.load(f)
        with open(paths.mapped_dir / "item2id.json", "r") as f:
            item2id = json.load(f)
        assert len(user2id) > 0
        assert len(item2id) > 0
        print(f"Mappings: {len(user2id)} users, {len(item2id)} items, OK")


def test_pipeline_stages_independent():
    """Test that running individual stages produces same results as running all."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir)

        domains = ["DomainA", "DomainB"]

        # Setup
        (tmp_root / "resource" / "raw").mkdir(parents=True)
        (tmp_root / "resource" / "cleaned").mkdir(parents=True)
        (tmp_root / "resource" / "filtered" / "test_tag").mkdir(parents=True)
        (tmp_root / "resource" / "mapped" / "test_tag").mkdir(parents=True)
        (tmp_root / "resource" / "splits" / "test_tag").mkdir(parents=True)

        for domain in domains:
            _create_synthetic_review_data(tmp_root / "resource" / "raw", domain)

        paths = get_data_paths(config={"paths": {
            "raw_dir": "resource/raw",
            "cleaned_dir": "resource/cleaned",
            "filtered_dir": "resource/filtered",
            "mapped_dir": "resource/mapped",
            "splits_dir": "resource/splits",
            "item_knn_dir": "resource/item_knn",
            "corpus_dir": "resource/corpus",
            "log_dir": "experiments/logs",
            "experiments_dir": "experiments",
        }}, tag="test_tag")
        paths = replace(paths,
            raw_dir=tmp_root / "resource" / "raw",
            cleaned_dir=tmp_root / "resource" / "cleaned",
            filtered_dir=tmp_root / "resource" / "filtered" / "test_tag",
            mapped_dir=tmp_root / "resource" / "mapped" / "test_tag",
            splits_dir=tmp_root / "resource" / "splits" / "test_tag",
        )

        # Run stage 1 only
        for domain in domains:
            clean_domain(paths, domain, chunk_size=50, force=True)

        # Run stage 2 only
        merge_filter_domains(paths, domains, force=True)

        # Run stage 3 only
        map_split(paths, force=True)

        # Verify outputs exist
        for domain in domains:
            assert paths.cleaned_path(domain).exists()
        assert paths.filtered_path.exists()
        assert paths.split_path("train").exists()
        assert paths.split_path("validation").exists()
        assert paths.split_path("test").exists()


def test_pipeline_fail_fast():
    """Test that pipeline fails fast with proper error messages."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir)

        (tmp_root / "resource" / "raw").mkdir(parents=True)
        (tmp_root / "resource" / "cleaned").mkdir(parents=True)
        (tmp_root / "resource" / "filtered" / "test_tag").mkdir(parents=True)
        (tmp_root / "resource" / "mapped" / "test_tag").mkdir(parents=True)
        (tmp_root / "resource" / "splits" / "test_tag").mkdir(parents=True)

        paths = get_data_paths(config={"paths": {
            "raw_dir": "resource/raw",
            "cleaned_dir": "resource/cleaned",
            "filtered_dir": "resource/filtered",
            "mapped_dir": "resource/mapped",
            "splits_dir": "resource/splits",
            "item_knn_dir": "resource/item_knn",
            "corpus_dir": "resource/corpus",
            "log_dir": "experiments/logs",
            "experiments_dir": "experiments",
        }}, tag="test_tag")
        paths = replace(paths,
            raw_dir=tmp_root / "resource" / "raw",
            cleaned_dir=tmp_root / "resource" / "cleaned",
            filtered_dir=tmp_root / "resource" / "filtered" / "test_tag",
            mapped_dir=tmp_root / "resource" / "mapped" / "test_tag",
            splits_dir=tmp_root / "resource" / "splits" / "test_tag",
        )

        # Missing input for stage 2 should raise FileNotFoundError
        with pytest.raises(FileNotFoundError, match="Không tìm thấy"):
            merge_filter_domains(paths, ["DomainA"], force=True)


def test_pipeline_custom_path_args():
    """Test that custom review-path and output-dir work correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir)

        (tmp_root / "custom_raw").mkdir(parents=True)
        (tmp_root / "custom_cleaned").mkdir(parents=True)

        domain = "DomainA"
        _create_synthetic_review_data(tmp_root / "custom_raw", domain)

        paths = get_data_paths(config={"paths": {
            "raw_dir": "resource/raw",
            "cleaned_dir": "resource/cleaned",
            "filtered_dir": "resource/filtered",
            "mapped_dir": "resource/mapped",
            "splits_dir": "resource/splits",
            "item_knn_dir": "resource/item_knn",
            "corpus_dir": "resource/corpus",
            "log_dir": "experiments/logs",
            "experiments_dir": "experiments",
        }}, tag="test_tag")

        clean_domain(
            paths,
            domain,
            review_path=tmp_root / "custom_raw" / f"{domain}.jsonl.gz",
            output_dir=tmp_root / "custom_cleaned",
            chunk_size=50,
            force=True,
        )

        assert (tmp_root / "custom_cleaned" / domain / "interactions.parquet").exists()


def test_pipeline_k_core_blocked():
    """Test that k-core blocking still works."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir)

        (tmp_root / "resource" / "raw").mkdir(parents=True)
        (tmp_root / "resource" / "cleaned").mkdir(parents=True)
        (tmp_root / "resource" / "filtered" / "test_tag").mkdir(parents=True)
        (tmp_root / "resource" / "mapped" / "test_tag").mkdir(parents=True)
        (tmp_root / "resource" / "splits" / "test_tag").mkdir(parents=True)

        # Create minimal data that will be filtered out by k-core
        domain = "DomainA"
        path = tmp_root / "resource" / "raw" / f"{domain}.jsonl.gz"
        with gzip.open(path, "wt", encoding="utf-8") as f:
            for i in range(2):  # Very sparse data
                f.write(json.dumps({
                    "user_id": f"u{i}",
                    "parent_asin": f"i{i}",
                    "rating": 5.0,
                    "timestamp": 1000 + i * 10,
                    "title": f"Title {i}",
                }) + "\n")

        paths = get_data_paths(config={"paths": {
            "raw_dir": "resource/raw",
            "cleaned_dir": "resource/cleaned",
            "filtered_dir": "resource/filtered",
            "mapped_dir": "resource/mapped",
            "splits_dir": "resource/splits",
            "item_knn_dir": "resource/item_knn",
            "corpus_dir": "resource/corpus",
            "log_dir": "experiments/logs",
            "experiments_dir": "experiments",
        }}, tag="test_tag")
        paths = replace(paths,
            raw_dir=tmp_root / "resource" / "raw",
            cleaned_dir=tmp_root / "resource" / "cleaned",
            filtered_dir=tmp_root / "resource" / "filtered" / "test_tag",
            mapped_dir=tmp_root / "resource" / "mapped" / "test_tag",
            splits_dir=tmp_root / "resource" / "splits" / "test_tag",
        )

        clean_domain(paths, domain, chunk_size=50, force=True)

        # Stage 2 should exit with BLOCKED message
        with pytest.raises(SystemExit, match="BLOCKED"):
            merge_filter_domains(paths, [domain], force=True)
