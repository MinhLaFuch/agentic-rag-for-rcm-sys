import gzip
import json

import pytest

from data.eda.meta_eda import compute_metadata_stats


@pytest.fixture
def synthetic_meta_file(tmp_path):
    records = [
        {
            "title": "Item A",
            "price": "19.99",
            "description": ["a desc"],
            "features": ["f1"],
            "store": "StoreA",
            "categories": ["Video Games", "PC"],
            "rating_number": 10,
            "average_rating": 4.5,
        },
        {
            "title": "Item B",
            "price": None,
            "description": [],
            "features": [],
            "store": None,
            "categories": ["Video Games", "PlayStation"],
            "rating_number": 0,
            "average_rating": None,
        },
        {
            "title": "Item C",
            "price": None,
            "description": ["c desc"],
            "features": ["f1", "f2"],
            "store": "StoreA",
            "categories": ["Video Games"],
            "rating_number": 5,
            "average_rating": 3.0,
        },
    ]
    path = tmp_path / "meta_test.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return path


def test_compute_metadata_stats_counts(synthetic_meta_file):
    stats = compute_metadata_stats(synthetic_meta_file)
    assert stats.num_items == 3
    assert stats.num_missing_price == 2
    assert stats.num_missing_description == 1
    assert stats.num_missing_features == 1
    assert stats.num_missing_store == 1


def test_compute_metadata_stats_category_and_store_distribution(synthetic_meta_file):
    stats = compute_metadata_stats(synthetic_meta_file)
    assert stats.category_counter["Video Games"] == 3
    assert stats.category_counter["PC"] == 1
    assert stats.store_counter["StoreA"] == 2


def test_compute_metadata_stats_rating_aggregates(synthetic_meta_file):
    stats = compute_metadata_stats(synthetic_meta_file)
    assert stats.rating_number_sum == 15
    assert stats.num_with_average_rating == 2
    assert stats.avg_average_rating == pytest.approx((4.5 + 3.0) / 2)


def test_compute_metadata_stats_respects_limit(synthetic_meta_file):
    stats = compute_metadata_stats(synthetic_meta_file, limit=1)
    assert stats.num_items == 1
