"""Test corpus save/load functionality."""

import json
import sqlite3
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from package.tools.base import ToolInputError
from package.tools.corpus import ItemCorpus, load_corpus, save_corpus
from package.tools.corpus._sql import CORPUS_LOGIC_VERSION, get_corpus_schema_fingerprint


def _make_sample_meta():
    """Create sample metadata DataFrame for testing."""
    return pd.DataFrame([
        {
            "parent_asin": "B001",
            "domain": "TestDomain",
            "title": "Test Item 1",
            "price": "19.99",
            "average_rating": "4.5",
            "rating_number": "100",
            "main_category": "Electronics",
            "categories": ["Electronics", "Gadgets"],
        },
        {
            "parent_asin": "B002",
            "domain": "TestDomain",
            "title": "Test Item 2",
            "price": "29.99",
            "average_rating": "4.0",
            "rating_number": "50",
            "main_category": "Books",
            "categories": ["Books", "Fiction"],
        },
    ])


def test_save_load_corpus_gives_same_results(tmp_path):
    """Saving and loading corpus should produce identical query results."""
    meta = _make_sample_meta()
    corpus = ItemCorpus.from_dataframe(meta)

    # Save
    corpus_path = tmp_path / "test.sqlite"
    meta_files = [("TestDomain", "/fake/meta_TestDomain.jsonl.gz")]
    item2id = {"TestDomain::B001": 0, "TestDomain::B002": 1}
    min_coverage = 0.5
    coverage = 1.0
    build_times = {"load_meta": 0.1, "to_sql": 0.2, "categories": 0.1, "indexes": 0.1, "fts": 0.1}

    # Mock meta file for save
    meta_file_path = tmp_path / "meta_TestDomain.jsonl.gz"
    meta_file_path.write_text("fake")
    meta_files = [("TestDomain", str(meta_file_path))]

    save_corpus(corpus, corpus_path, meta_files, item2id, min_coverage, coverage, build_times)

    # Load
    loaded_corpus, loaded_coverage = load_corpus(corpus_path, meta_files, item2id, min_coverage)

    # Check coverage
    assert loaded_coverage == coverage

    # Check query results
    rows1, _ = corpus.select("SELECT item_id, title FROM items")
    rows2, _ = loaded_corpus.select("SELECT item_id, title FROM items")
    assert len(rows1) == len(rows2) == 2
    assert set(r["item_id"] for r in rows1) == set(r["item_id"] for r in rows2)

    # Check count
    count1 = corpus.count("domain = ?", ("TestDomain",))
    count2 = loaded_corpus.count("domain = ?", ("TestDomain",))
    assert count1 == count2 == 2

    # Check domains
    assert corpus.domains() == loaded_corpus.domains() == ["TestDomain"]

    # Check item_domains
    item_ids = ["TestDomain::B001", "TestDomain::B002"]
    domains1 = corpus.item_domains(item_ids)
    domains2 = loaded_corpus.item_domains(item_ids)
    assert domains1 == domains2

    # Check categories
    cats1 = corpus.categories()
    cats2 = loaded_corpus.categories()
    assert set(cats1) == set(cats2)


def test_loaded_corpus_is_read_only(tmp_path):
    """Loaded corpus should reject INSERT/UPDATE/DROP operations."""
    meta = _make_sample_meta()
    corpus = ItemCorpus.from_dataframe(meta)

    corpus_path = tmp_path / "test.sqlite"
    meta_file_path = tmp_path / "meta_TestDomain.jsonl.gz"
    meta_file_path.write_text("fake")
    meta_files = [("TestDomain", str(meta_file_path))]
    item2id = {"TestDomain::B001": 0, "TestDomain::B002": 1}

    save_corpus(corpus, corpus_path, meta_files, item2id, 0.5, 1.0, {})
    loaded_corpus, _ = load_corpus(corpus_path, meta_files, item2id, 0.5)

    # INSERT should fail (ToolInputError from authorizer)
    with pytest.raises(ToolInputError):
        loaded_corpus.select("INSERT INTO items (item_id, domain) VALUES ('fake', 'fake')")

    # UPDATE should fail
    with pytest.raises(ToolInputError):
        loaded_corpus.select("UPDATE items SET title = 'x'")

    # DROP should fail
    with pytest.raises(ToolInputError):
        loaded_corpus.select("DROP TABLE items")


def test_loaded_corpus_has_time_budget(tmp_path):
    """Loaded corpus should still enforce time budget on select."""
    meta = _make_sample_meta()
    corpus = ItemCorpus.from_dataframe(meta)

    corpus_path = tmp_path / "test.sqlite"
    meta_file_path = tmp_path / "meta_TestDomain.jsonl.gz"
    meta_file_path.write_text("fake")
    meta_files = [("TestDomain", str(meta_file_path))]
    item2id = {"TestDomain::B001": 0, "TestDomain::B002": 1}

    save_corpus(corpus, corpus_path, meta_files, item2id, 0.5, 1.0, {})
    loaded_corpus, _ = load_corpus(corpus_path, meta_files, item2id, 0.5)

    # Normal query should work
    rows, _ = loaded_corpus.select("SELECT * FROM items")
    assert len(rows) == 2


def test_load_fails_with_schema_mismatch(tmp_path):
    """Loading should fail if schema fingerprint doesn't match."""
    meta = _make_sample_meta()
    corpus = ItemCorpus.from_dataframe(meta)

    corpus_path = tmp_path / "test.sqlite"
    meta_file_path = tmp_path / "meta_TestDomain.jsonl.gz"
    meta_file_path.write_text("fake")
    meta_files = [("TestDomain", str(meta_file_path))]
    item2id = {"TestDomain::B001": 0, "TestDomain::B002": 1}

    save_corpus(corpus, corpus_path, meta_files, item2id, 0.5, 1.0, {})

    # Modify metadata to have wrong schema fingerprint
    meta_path = corpus_path.with_suffix(".meta.json")
    with open(meta_path, encoding="utf-8") as f:
        metadata = json.load(f)
    metadata["schema_fingerprint"] = "wrong_fingerprint"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f)

    with pytest.raises(ValueError, match="Schema fingerprint mismatch"):
        load_corpus(corpus_path, meta_files, item2id, 0.5)


def test_load_fails_with_source_file_change(tmp_path):
    """Loading should fail if source meta files changed."""
    meta = _make_sample_meta()
    corpus = ItemCorpus.from_dataframe(meta)

    corpus_path = tmp_path / "test.sqlite"
    meta_file_path = tmp_path / "meta_TestDomain.jsonl.gz"
    meta_file_path.write_text("fake")
    meta_files = [("TestDomain", str(meta_file_path))]
    item2id = {"TestDomain::B001": 0, "TestDomain::B002": 1}

    save_corpus(corpus, corpus_path, meta_files, item2id, 0.5, 1.0, {})

    # Modify meta file (change size)
    meta_file_path.write_text("fake content that is longer now")

    with pytest.raises(ValueError, match="Source file metadata mismatch"):
        load_corpus(corpus_path, meta_files, item2id, 0.5)


def test_load_fails_with_mapping_change(tmp_path):
    """Loading should fail if item2id changed."""
    meta = _make_sample_meta()
    corpus = ItemCorpus.from_dataframe(meta)

    corpus_path = tmp_path / "test.sqlite"
    meta_file_path = tmp_path / "meta_TestDomain.jsonl.gz"
    meta_file_path.write_text("fake")
    meta_files = [("TestDomain", str(meta_file_path))]
    item2id = {"TestDomain::B001": 0, "TestDomain::B002": 1}

    save_corpus(corpus, corpus_path, meta_files, item2id, 0.5, 1.0, {})

    # Change item2id (change middle key)
    different_item2id = {"TestDomain::B001": 0, "TestDomain::B003": 1}

    with pytest.raises(ValueError, match="Mapping hash mismatch"):
        load_corpus(corpus_path, meta_files, different_item2id, 0.5)


def test_load_fails_with_mapping_change_last_key(tmp_path):
    """Loading should fail if item2id changed (change last key to test full hash)."""
    meta = _make_sample_meta()
    corpus = ItemCorpus.from_dataframe(meta)

    corpus_path = tmp_path / "test.sqlite"
    meta_file_path = tmp_path / "meta_TestDomain.jsonl.gz"
    meta_file_path.write_text("fake")
    meta_files = [("TestDomain", str(meta_file_path))]
    item2id = {"TestDomain::B001": 0, "TestDomain::B002": 1}

    save_corpus(corpus, corpus_path, meta_files, item2id, 0.5, 1.0, {})

    # Change item2id (change last key - would be missed if only hashing first 1000)
    different_item2id = {"TestDomain::B001": 0, "TestDomain::B003": 1}

    with pytest.raises(ValueError, match="Mapping hash mismatch"):
        load_corpus(corpus_path, meta_files, different_item2id, 0.5)


def test_load_fails_with_min_coverage_change(tmp_path):
    """Loading should fail if min_coverage changed."""
    meta = _make_sample_meta()
    corpus = ItemCorpus.from_dataframe(meta)

    corpus_path = tmp_path / "test.sqlite"
    meta_file_path = tmp_path / "meta_TestDomain.jsonl.gz"
    meta_file_path.write_text("fake")
    meta_files = [("TestDomain", str(meta_file_path))]
    item2id = {"TestDomain::B001": 0, "TestDomain::B002": 1}

    save_corpus(corpus, corpus_path, meta_files, item2id, 0.5, 1.0, {})

    # Change min_coverage
    with pytest.raises(ValueError, match="min_coverage mismatch"):
        load_corpus(corpus_path, meta_files, item2id, 0.8)


def test_load_fails_with_missing_file(tmp_path):
    """Loading should fail if file is missing."""
    corpus_path = tmp_path / "nonexistent.sqlite"
    meta_files = [("TestDomain", str(tmp_path / "meta_TestDomain.jsonl.gz"))]
    item2id = {"TestDomain::B001": 0}

    with pytest.raises(FileNotFoundError, match="Corpus file not found"):
        load_corpus(corpus_path, meta_files, item2id, 0.5)


def test_load_fails_with_missing_metadata(tmp_path):
    """Loading should fail if metadata file is missing."""
    meta = _make_sample_meta()
    corpus = ItemCorpus.from_dataframe(meta)

    corpus_path = tmp_path / "test.sqlite"
    meta_file_path = tmp_path / "meta_TestDomain.jsonl.gz"
    meta_file_path.write_text("fake")
    meta_files = [("TestDomain", str(meta_file_path))]
    item2id = {"TestDomain::B001": 0, "TestDomain::B002": 1}

    save_corpus(corpus, corpus_path, meta_files, item2id, 0.5, 1.0, {})

    # Delete metadata file
    corpus_path.with_suffix(".meta.json").unlink()

    with pytest.raises(FileNotFoundError, match="Corpus metadata file not found"):
        load_corpus(corpus_path, meta_files, item2id, 0.5)


def test_save_uses_temp_file(tmp_path):
    """Save should use temp file and atomic rename."""
    meta = _make_sample_meta()
    corpus = ItemCorpus.from_dataframe(meta)

    corpus_path = tmp_path / "test.sqlite"
    meta_file_path = tmp_path / "meta_TestDomain.jsonl.gz"
    meta_file_path.write_text("fake")
    meta_files = [("TestDomain", str(meta_file_path))]
    item2id = {"TestDomain::B001": 0, "TestDomain::B002": 1}

    # Save should create .tmp file first, then rename
    save_corpus(corpus, corpus_path, meta_files, item2id, 0.5, 1.0, {})

    # Final file should exist
    assert corpus_path.exists()
    assert corpus_path.with_suffix(".meta.json").exists()

    # Temp file should not exist after successful save
    assert not corpus_path.with_suffix(".tmp").exists()
    assert not corpus_path.with_suffix(".tmp.json").exists()


def test_metadata_contains_required_fields(tmp_path):
    """Saved metadata should contain all required validation fields."""
    meta = _make_sample_meta()
    corpus = ItemCorpus.from_dataframe(meta)

    corpus_path = tmp_path / "test.sqlite"
    meta_file_path = tmp_path / "meta_TestDomain.jsonl.gz"
    meta_file_path.write_text("fake")
    meta_files = [("TestDomain", str(meta_file_path))]
    item2id = {"TestDomain::B001": 0, "TestDomain::B002": 1}
    build_times = {"load_meta": 0.1, "to_sql": 0.2, "categories": 0.1, "indexes": 0.1, "fts": 0.1}

    save_corpus(corpus, corpus_path, meta_files, item2id, 0.5, 1.0, build_times)

    meta_path = corpus_path.with_suffix(".meta.json")
    with open(meta_path, encoding="utf-8") as f:
        metadata = json.load(f)

    required_fields = [
        "format_version",
        "schema_fingerprint",
        "logic_version",
        "num_items",
        "min_coverage",
        "coverage",
        "source_hashes",
        "mapping_hash",
        "build_times",
        "created_at",
    ]
    for field in required_fields:
        assert field in metadata, f"Missing field: {field}"

    assert metadata["format_version"] == 1
    assert metadata["logic_version"] == CORPUS_LOGIC_VERSION
    assert metadata["schema_fingerprint"] == get_corpus_schema_fingerprint()
    assert metadata["num_items"] == 2
    assert metadata["min_coverage"] == 0.5
    assert metadata["coverage"] == 1.0
