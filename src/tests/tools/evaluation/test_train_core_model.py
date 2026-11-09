import json
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from package.config import get_data_paths
from package.evaluation.recommender.analysis.build_core_model import build_core_model
from package.evaluation.recommender.analysis.core_inputs import core_inputs
from package.evaluation.recommender.analysis.global_core_pairs import global_core_pairs
from package.recommenders import ItemKNNRecommender
from package.recommenders.shared.save_item_knn import save_item_knn
from package.tools.scoring import BaselineScorer


@pytest.fixture
def core_tag(tmp_path):
    paths = replace(get_data_paths("toy"), mapped_dir=tmp_path / "mapped",
                    splits_dir=tmp_path / "splits", item_knn_dir=tmp_path / "knn")
    (paths.mapped_dir / "fit_core").mkdir(parents=True)
    paths.splits_dir.mkdir()
    paths.item_knn_dir.mkdir()
    (paths.splits_dir / "stage_3.manifest.json").write_text(json.dumps(
        {"flags": {"data_protocol": "temporal_train_core"}}))
    # Local indices deliberately differ from the evaluation indices.
    users, items = {"u": 0}, {"b": 0, "a": 1}
    for name, mapping in (("user2id", users), ("item2id", items)):
        (paths.mapped_dir / "fit_core" / (name + ".json")).write_text(json.dumps(mapping))
    pairs = pd.DataFrame({"user_idx": [0, 0], "item_idx": [0, 1]})
    pairs.to_parquet(paths.splits_dir / "train_core.parquet")
    save_item_knn(ItemKNNRecommender(1).fit(pairs), paths.item_knn_path("validation"),
                  1, pairs, user2id=users, item2id=items, eval_on="validation", tag="toy",
                  fit_splits=["train_core"])
    return paths


def test_cache_remapping_retains_non_core_history_without_learning_from_it(core_tag):
    users, items = {"outside": 0, "u": 1}, {"a": 0, "untrained": 1, "b": 2}
    history = pd.DataFrame({"user_idx": [0, 0, 1], "item_idx": [0, 1, 2]})
    model = build_core_model(core_tag, "validation", 1, history, users, items)
    assert model._evaluation_artifact_status == "validated_train_core_cache"
    assert model.similarity.shape == (3, 3)
    assert model.similarity[0, 2] == 1
    assert model.similarity[1].nnz == 0
    assert model.scores.tolist() == [1, 0, 1]
    assert BaselineScorer(model, popularity_weight=0).score(0, np.array([2]))[0] == 1
    assert BaselineScorer(model).seen_items(0) == {0, 1}
    assert global_core_pairs(core_inputs(core_tag, users, items)).item_idx.tolist() == [2, 0]


def test_incompatible_cache_fails_instead_of_silently_refitting(core_tag):
    with pytest.raises(ValueError, match="k mismatch"):
        build_core_model(core_tag, "validation", 2,
                         pd.DataFrame({"user_idx": [0], "item_idx": [0]}),
                         {"u": 0}, {"a": 0, "b": 1})


@pytest.mark.parametrize("hybrid", [False, True])
@pytest.mark.parametrize("popularity_source", ["train_core", "full_history"])
def test_baseline_runner_uses_core_cache_and_full_history_segments(core_tag, monkeypatch, hybrid, popularity_source):
    import sys
    from benchmarks import run_baselines as script

    users, items = {"outside": 0, "u": 1}, {"a": 0, "untrained": 1, "b": 2}
    for name, mapping in (("user2id", users), ("item2id", items)):
        (core_tag.mapped_dir / (name + ".json")).write_text(json.dumps(mapping))
    train = pd.DataFrame({"user_idx": [0, 1, 1], "item_idx": [0, 0, 2], "timestamp": [1]*3})
    target = pd.DataFrame({"user_idx": [0, 1], "item_idx": [2, 1], "timestamp": [2]*2})
    for name, frame in (("train", train), ("validation", target), ("test", target.assign(timestamp=3))):
        frame.to_parquet(core_tag.split_path(name))
    monkeypatch.setattr(script, "get_data_paths", lambda *a, **k: core_tag)
    load = script.load_config
    # Tunables live in eval/baselines.yaml (Phase 5: no CLI overrides) — the
    # monkeypatched config plays the role of that YAML for this fixture.
    monkeypatch.setattr(script, "load_config", lambda name: (
        {"baselines": {
            "models": ["popularity", "item_knn"], "seed": 42, "popularity_fallback": True,
            "item_knn": {"k": 1},
            "popularity_source": popularity_source,
            "item_knn_hybrid_weight": 4.0 if hybrid else None}}
        if name == "eval/baselines"
        else {"recommendation_metrics": {"k_values": [1]}}
        if name == "eval/recommendation_metrics"
        else load(name)))
    saved = {}
    def save(*args, **kwargs):
        saved.update(kwargs)
        return "fixture"
    monkeypatch.setattr(script, "save_experiment", save)
    monkeypatch.setattr(script, "next_experiment_dir", lambda *a: "fixture")
    monkeypatch.setattr(sys, "argv", ["run_baselines"])
    script.main()
    assert saved["config"]["fit_splits"] == ["train_core"]
    assert saved["config"]["popularity_source"] == popularity_source
    assert ("history_popularity" if popularity_source == "full_history" else "popularity") in saved["metrics"]
    pop_name="history_popularity" if popularity_source=="full_history" else "popularity"
    assert saved["config"]["fit_splits_by_model"][pop_name] == (["train"] if popularity_source=="full_history" else ["train_core"])
    if hybrid:
        assert "hybrid_item_knn_w4" in saved["metrics"]
        assert saved["config"]["hybrid_popularity_source"] == "full pre-target history"
    for result in saved["metrics"].values():
        assert result["num_users"]["all"] == 2
        assert result["num_users"]["sparse"] == 2
