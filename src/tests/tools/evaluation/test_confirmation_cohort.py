import pytest
import yaml
import numpy as np

from package.tools.evaluation.confirmation_cohort import confirmation_cohort


def manifest(tmp_path, **updates):
    dataset = dict(tag="d", eval_on="validation", user_mapping_hash="u", mapping_hash="i")
    dataset.update(updates)
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump({"run": {"dataset": dataset},
                                "config": {"sampled_user_ids": {"cold": [1, 2], "warm": [2, 3]}}}))
    return p


def read(paths):
    return confirmation_cohort(paths, tag="d", split="validation", user_hash="u", item_hash="i")


def test_exclusion_union_and_empty(tmp_path):
    p = manifest(tmp_path)
    assert read([p, p]) == {1, 2, 3}
    assert read([]) == set()


@pytest.mark.parametrize("key", ["tag", "eval_on", "user_mapping_hash", "mapping_hash"])
def test_incompatible_manifest_rejected(tmp_path, key):
    with pytest.raises(ValueError, match=key):
        read([manifest(tmp_path, **{key: "wrong"})])


def test_invalid_indices_rejected(tmp_path):
    p = manifest(tmp_path)
    doc = yaml.safe_load(p.read_text())
    doc["config"]["sampled_user_ids"]["cold"] = [True]
    p.write_text(yaml.safe_dump(doc))
    with pytest.raises(ValueError, match="invalid user"):
        read([p])


def test_seeded_sample_is_disjoint_after_exclusion(tmp_path):
    from scripts.evaluation.candidate_recall import sample_users
    excluded = read([manifest(tmp_path)])
    population = {u: "cold" for u in range(10) if u not in excluded}
    first = sample_users(population, 4, np.random.default_rng(42))
    assert first == sample_users(population, 4, np.random.default_rng(42))
    assert not excluded.intersection(first["cold"])
    assert len(first["cold"]) == 4


def test_empty_manifest_rejected(tmp_path):
    p = manifest(tmp_path)
    doc = yaml.safe_load(p.read_text())
    doc["config"]["sampled_user_ids"] = {"cold": []}
    p.write_text(yaml.safe_dump(doc))
    with pytest.raises(ValueError, match="empty sample"):
        read([p])
