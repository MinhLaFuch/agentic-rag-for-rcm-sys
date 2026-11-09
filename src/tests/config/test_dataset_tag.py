"""Regression tests for domain-derived dataset tags (Phase 5)."""

import pytest

from package.config import get_data_paths, resolve_dataset_tag
from package.config._constants import PROJECT_ROOT


def test_no_selection_resolves_to_merged_name():
    assert resolve_dataset_tag() == "multi_domain"
    assert resolve_dataset_tag([]) == "multi_domain"


def test_all_domains_any_order_resolves_to_merged_name():
    assert resolve_dataset_tag(["Video_Games", "Toys_and_Games", "Electronics"]) == "multi_domain"
    assert resolve_dataset_tag(["Electronics", "Video_Games", "Toys_and_Games"]) == "multi_domain"


def test_single_domain_resolves_to_domain_name():
    assert resolve_dataset_tag(["Video_Games"]) == "Video_Games"
    assert resolve_dataset_tag(["Toys_and_Games"]) == "Toys_and_Games"
    assert resolve_dataset_tag(["Electronics"]) == "Electronics"


def test_duplicate_single_domain_still_resolves():
    assert resolve_dataset_tag(["Video_Games", "Video_Games"]) == "Video_Games"


def test_two_domain_subset_is_rejected():
    with pytest.raises(ValueError, match="domain subset"):
        resolve_dataset_tag(["Video_Games", "Electronics"])


def test_unknown_domain_is_rejected():
    with pytest.raises(ValueError, match="Unknown domain"):
        resolve_dataset_tag(["Not_A_Domain"])


def test_get_data_paths_derives_tag_from_domains():
    paths = get_data_paths(domains=["Video_Games"])
    assert paths.tag == "Video_Games"
    assert paths.splits_dir == PROJECT_ROOT / "resource" / "splits" / "Video_Games"
    assert paths.filtered_path == PROJECT_ROOT / "resource" / "filtered" / "Video_Games" / "interactions.parquet"
    assert paths.log_dir == PROJECT_ROOT / "experiments" / "logs" / "Video_Games"


def test_get_data_paths_default_is_merged():
    paths = get_data_paths()
    assert paths.tag == "multi_domain"
    assert paths.splits_dir == PROJECT_ROOT / "resource" / "splits" / "multi_domain"


def test_get_data_paths_explicit_tag_override_still_works():
    """Low-level override kept for tests and old-experiment manifests."""
    paths = get_data_paths(tag="legacy_tag")
    assert paths.tag == "legacy_tag"
    assert paths.splits_dir.name == "legacy_tag"
