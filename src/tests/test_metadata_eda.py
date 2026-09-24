import pytest

from package.data.eda import meta_eda
from package.data.eda.metadata_stat import MetadataStats


@pytest.fixture
def synthetic_meta_file(tmp_path, write_jsonl_gz):
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
    return write_jsonl_gz(tmp_path / "meta_test.jsonl.gz", records)


# ---------------------------------------------------------------- meta_eda


def test_meta_eda_counts(synthetic_meta_file):
    stats = meta_eda(synthetic_meta_file)
    assert stats.num_items == 3
    assert stats.num_missing_price == 2
    assert stats.num_missing_description == 1
    assert stats.num_missing_features == 1
    assert stats.num_missing_store == 1


def test_meta_eda_category_and_store_distribution(synthetic_meta_file):
    stats = meta_eda(synthetic_meta_file)
    assert stats.category_counter["Video Games"] == 3
    assert stats.category_counter["PC"] == 1
    assert stats.store_counter["StoreA"] == 2


def test_meta_eda_rating_aggregates(synthetic_meta_file):
    stats = meta_eda(synthetic_meta_file)
    assert stats.rating_number_sum == 15
    assert stats.num_with_average_rating == 2
    assert stats.num_missing_average_rating == 1
    assert stats.avg_average_rating == pytest.approx((4.5 + 3.0) / 2)


def test_meta_eda_respects_limit(synthetic_meta_file):
    assert meta_eda(synthetic_meta_file, limit=1).num_items == 1
    assert meta_eda(synthetic_meta_file, limit=0).num_items == 0
    assert meta_eda(synthetic_meta_file, limit=100).num_items == 3


@pytest.mark.parametrize("empty_price", [None, "", "null"])
def test_meta_eda_treats_none_empty_and_null_string_as_missing_price(tmp_path, write_jsonl_gz, empty_price):
    path = write_jsonl_gz(tmp_path / "meta.jsonl.gz", [{"title": "x", "price": empty_price}])
    assert meta_eda(path).num_missing_price == 1


def test_meta_eda_tolerates_missing_fields_and_null_categories(tmp_path, write_jsonl_gz):
    path = write_jsonl_gz(tmp_path / "meta.jsonl.gz", [{"title": "bare"}, {"title": "n", "categories": None}])
    stats = meta_eda(path)
    assert stats.num_items == 2
    assert stats.num_missing_description == 2
    assert not stats.category_counter


def test_meta_eda_ignores_non_numeric_ratings(tmp_path, write_jsonl_gz):
    path = write_jsonl_gz(
        tmp_path / "meta.jsonl.gz", [{"title": "x", "rating_number": "12", "average_rating": "4.5"}]
    )
    stats = meta_eda(path)
    assert stats.rating_number_sum == 0
    assert stats.num_with_average_rating == 0
    assert stats.num_missing_average_rating == 1


def test_meta_eda_empty_file(tmp_path, write_jsonl_gz):
    stats = meta_eda(write_jsonl_gz(tmp_path / "empty.jsonl.gz", []))
    assert stats.num_items == 0


# ----------------------------------------------------------- MetadataStats


def test_metadata_stats_percentages(synthetic_meta_file):
    stats = meta_eda(synthetic_meta_file)
    assert stats.pct_missing_price == pytest.approx(2 / 3)
    assert stats.pct_missing_description == pytest.approx(1 / 3)
    assert stats.pct_missing_features == pytest.approx(1 / 3)
    assert stats.pct_missing_store == pytest.approx(1 / 3)


def test_metadata_stats_averages(synthetic_meta_file):
    stats = meta_eda(synthetic_meta_file)
    assert stats.avg_rating_number == pytest.approx(15 / 3)  # divides by ALL items, rated or not
    assert stats.avg_average_rating == pytest.approx(3.75)  # divides by items that have a rating


def test_metadata_stats_empty_defaults_are_zero_not_division_errors():
    stats = MetadataStats()
    assert stats.pct_missing_price == 0.0
    assert stats.pct_missing_description == 0.0
    assert stats.pct_missing_features == 0.0
    assert stats.pct_missing_store == 0.0
    assert stats.avg_rating_number == 0.0
    assert stats.avg_average_rating == 0.0


def test_metadata_stats_instances_do_not_share_counters():
    first, second = MetadataStats(), MetadataStats()
    first.category_counter["x"] += 1
    assert "x" not in second.category_counter
