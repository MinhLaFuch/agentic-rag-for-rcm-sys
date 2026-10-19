"""Tests for ItemKNN save/load functionality."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sp

from package.tools.recommenders import ItemKNNRecommender
from package.tools.recommenders.load_item_knn import load_item_knn
from package.tools.recommenders.save_item_knn import save_item_knn


def test_save_load_same_similarity():
    """Save and load should produce identical similarity matrix."""
    # Create synthetic data
    fit_pairs = pd.DataFrame({
        "user_idx": [0, 0, 1, 1, 2, 2, 2],
        "item_idx": [0, 1, 1, 2, 0, 1, 2],
    })
    k = 2

    # Fit model
    model = ItemKNNRecommender(k).fit(fit_pairs)

    # Save
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "model.npz"
        save_item_knn(model, path, k, fit_pairs)

        # Load
        loaded_model = load_item_knn(path, k, fit_pairs)

        # Compare similarity matrices
        assert loaded_model.similarity.shape == model.similarity.shape
        assert np.allclose(
            loaded_model.similarity.data, model.similarity.data
        ), "Similarity matrices should be identical"
        assert np.array_equal(
            loaded_model.similarity.indices, model.similarity.indices
        )
        assert np.array_equal(
            loaded_model.similarity.indptr, model.similarity.indptr
        )


def test_load_with_wrong_k():
    """Loading with different k should raise ValueError."""
    fit_pairs = pd.DataFrame({
        "user_idx": [0, 0, 1, 1],
        "item_idx": [0, 1, 1, 2],
    })
    k = 2

    model = ItemKNNRecommender(k).fit(fit_pairs)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "model.npz"
        save_item_knn(model, path, k, fit_pairs)

        # Try to load with different k
        with pytest.raises(ValueError, match="k mismatch"):
            load_item_knn(path, k + 1, fit_pairs)


def test_load_with_changed_data():
    """Loading with changed fit data should raise ValueError."""
    fit_pairs = pd.DataFrame({
        "user_idx": [0, 0, 1, 1],
        "item_idx": [0, 1, 1, 2],
    })
    k = 2

    model = ItemKNNRecommender(k).fit(fit_pairs)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "model.npz"
        save_item_knn(model, path, k, fit_pairs)

        # Change data by adding one interaction
        changed_pairs = pd.DataFrame({
            "user_idx": [0, 0, 1, 1, 2],
            "item_idx": [0, 1, 1, 2, 0],
        })

        with pytest.raises(ValueError, match="Data hash mismatch"):
            load_item_knn(path, k, changed_pairs)


def test_load_missing_file():
    """Loading from non-existent file should raise FileNotFoundError."""
    fit_pairs = pd.DataFrame({
        "user_idx": [0, 0],
        "item_idx": [0, 1],
    })

    with pytest.raises(FileNotFoundError, match="ItemKNN file not found"):
        load_item_knn(Path("/nonexistent/model.npz"), 2, fit_pairs)


def test_load_missing_metadata():
    """Loading when metadata file is missing should raise FileNotFoundError."""
    fit_pairs = pd.DataFrame({
        "user_idx": [0, 0],
        "item_idx": [0, 1],
    })
    k = 2

    model = ItemKNNRecommender(k).fit(fit_pairs)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "model.npz"
        save_item_knn(model, path, k, fit_pairs)

        # Delete metadata file
        path.with_suffix(".meta.json").unlink()

        with pytest.raises(FileNotFoundError, match="metadata file not found"):
            load_item_knn(path, k, fit_pairs)


def test_save_creates_files():
    """Save should create both npz and metadata files."""
    fit_pairs = pd.DataFrame({
        "user_idx": [0, 0, 1, 1],
        "item_idx": [0, 1, 1, 2],
    })
    k = 2

    model = ItemKNNRecommender(k).fit(fit_pairs)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "model.npz"
        save_item_knn(model, path, k, fit_pairs)

        # Verify final file exists
        assert path.exists()
        assert path.with_suffix(".meta.json").exists()


def test_loaded_model_produces_same_recommendations():
    """Loaded model should produce same recommendations as original."""
    fit_pairs = pd.DataFrame({
        "user_idx": [0, 0, 1, 1, 2, 2, 2, 3, 3],
        "item_idx": [0, 1, 1, 2, 0, 1, 2, 0, 3],
    })
    k = 2

    model = ItemKNNRecommender(k).fit(fit_pairs)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "model.npz"
        save_item_knn(model, path, k, fit_pairs)
        loaded_model = load_item_knn(path, k, fit_pairs)

        # Test recommendations for a specific user
        user_idx = 1
        top_k = 3
        original_recs = model.recommend(user_idx, top_k)
        loaded_recs = loaded_model.recommend(user_idx, top_k)

        assert original_recs == loaded_recs, "Recommendations should be identical"


def test_loaded_model_attributes():
    """Loaded model should have all required attributes reconstructed."""
    fit_pairs = pd.DataFrame({
        "user_idx": [0, 0, 1, 1, 2],
        "item_idx": [0, 1, 1, 2, 0],
    })
    k = 2

    model = ItemKNNRecommender(k).fit(fit_pairs)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "model.npz"
        save_item_knn(model, path, k, fit_pairs)
        loaded_model = load_item_knn(path, k, fit_pairs)

        # Check cheap attributes are reconstructed
        assert hasattr(loaded_model, "similarity")
        assert hasattr(loaded_model, "user_items")
        assert hasattr(loaded_model, "scores")
        assert hasattr(loaded_model, "ranked_items")
        assert hasattr(loaded_model, "num_items")

        # Check shapes match
        assert loaded_model.user_items.shape == model.user_items.shape
        assert len(loaded_model.scores) == len(model.scores)
        assert len(loaded_model.ranked_items) == len(model.ranked_items)


def test_corrupted_file():
    """Loading from corrupted file should raise error."""
    fit_pairs = pd.DataFrame({
        "user_idx": [0, 0],
        "item_idx": [0, 1],
    })
    k = 2

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "model.npz"
        # Write garbage
        path.write_text("corrupted data", encoding="utf-8")

        with pytest.raises(Exception):  # scipy.sparse.load_npz will raise
            load_item_knn(path, k, fit_pairs)
