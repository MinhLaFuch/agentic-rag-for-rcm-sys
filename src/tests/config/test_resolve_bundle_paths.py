import pytest

from package.config import get_data_paths
from package.config.resolve_bundle_paths import resolve_bundle_paths


def test_default_selection_is_unchanged():
    assert resolve_bundle_paths() == get_data_paths()


def test_explicit_audit_bundle():
    paths = resolve_bundle_paths(tag="multi_domain_v2_audit_20261030")
    assert paths.tag == "multi_domain_v2_audit_20261030"
    assert paths.splits_dir.name == paths.tag
    assert paths.mapped_dir.name == paths.tag
    assert paths.corpus_path.name == f"corpus_{paths.tag}.sqlite"


@pytest.mark.parametrize("tag", ["../escape", "C:\\data", "/absolute", "", "a/b", "a\\b", ".", ".."])
def test_rejects_unsafe_tags(tag):
    with pytest.raises(ValueError, match="Bundle tag"):
        resolve_bundle_paths(tag=tag)


def test_tag_does_not_disable_domain_validation():
    with pytest.raises(ValueError, match="Unknown domain"):
        resolve_bundle_paths(tag="audit", domains=["unknown"])
