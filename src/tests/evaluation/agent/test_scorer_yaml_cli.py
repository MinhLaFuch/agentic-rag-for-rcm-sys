"""TB-adapted equivalent of source ``test_agent_scorer_cli.py``.

Source tested ``--scorer`` / ``--hybrid-popularity-weight`` CLI flags; G2
removed those flags on purpose (Phase 5: tunables live in YAML only), so the
equivalent coverage injects ``agent/scoring`` via ``CONFIG_OVERLAY_PATH`` and
asserts the recorded experiment config + type1 trajectory fields.
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest
import yaml

from package.config import get_data_paths
from package.corpus import ItemCorpus
from scripts.evaluation import run_agent_eval as script


@pytest.fixture
def environment(tmp_path, monkeypatch):
    paths = replace(
        get_data_paths("toy"),
        raw_dir=tmp_path / "raw", mapped_dir=tmp_path / "mapped",
        splits_dir=tmp_path / "splits", corpus_dir=tmp_path / "corpus",
        cleaned_dir=tmp_path / "cleaned", filtered_dir=tmp_path / "filtered",
        item_knn_dir=tmp_path / "knn", log_dir=tmp_path / "logs",
        experiments_dir=tmp_path / "experiments",
    )
    for d in (paths.raw_dir, paths.mapped_dir, paths.splits_dir, paths.cleaned_dir,
              paths.log_dir, paths.experiments_dir):
        d.mkdir(parents=True, exist_ok=True)
    (paths.raw_dir / "meta_D.jsonl.gz").write_text("fixture metadata")

    user2id = {"u0": 0, "u1": 1, "u2": 2}
    item2id = {f"D::i{i}": i for i in range(7)}
    for name, mapping in (("user2id", user2id), ("item2id", item2id)):
        (paths.mapped_dir / f"{name}.json").write_text(json.dumps(mapping))

    train = pd.DataFrame({
        "user_idx": [0, 0, 2, 2, 2, 2, 2, 2],
        "item_idx": [0, 1, 0, 1, 2, 3, 4, 5],
        "timestamp": [1] * 8,
    })
    val = pd.DataFrame({
        "user_idx": [0, 1, 2], "item_idx": [2, 3, 6], "timestamp": [2] * 3,
    })
    test = val.assign(timestamp=3)
    for name, df in (("train", train), ("validation", val), ("test", test)):
        df.to_parquet(paths.split_path(name), index=False)

    meta = pd.DataFrame({
        "parent_asin": [f"i{i}" for i in range(7)], "domain": ["D"] * 7,
        "first_seen_ts": [1] * 7, "title": ["keyboard"] * 7,
        "price": [10.0 + i for i in range(7)],
        "average_rating": [4.0] * 7, "rating_number": [10] * 7,
        "store": ["shop"] * 7, "categories": [["Electronics", "Keyboards"]] * 7,
    })
    corpus = ItemCorpus.from_dataframe(meta)

    monkeypatch.setattr(script, "get_data_paths", lambda *a, **k: paths)
    monkeypatch.setattr(script, "get_domains", lambda: ["D"])
    monkeypatch.setattr(script, "verify_tag_manifest",
                        lambda *a, **k: {"status": "match", "manifest_sha256": "fixture", "warnings": []})
    monkeypatch.setattr(script, "build_meta_files",
                        lambda *a: [("D", str(paths.raw_dir / "meta_D.jsonl.gz"))])
    monkeypatch.setattr(script, "load_mappings", lambda *a: (user2id, item2id))
    monkeypatch.setattr(script, "build_first_seen_timestamps",
                        lambda *a, **k: {item: 1 for item in item2id})
    monkeypatch.setattr(script, "build_corpus",
                        lambda *a, **k: (corpus, meta, 1.0, {}))
    return tmp_path, paths, item2id


def _launch(monkeypatch, base: Path, name: str, *, mode: str) -> Path:
    overlay = {
        "agent/agent_eval": {"agent_eval": {
            "agents": ["baseline", "type1"], "k": 3, "per_segment": 1,
            "n_ambiguous": 0, "request_scope": "all", "use_prebuilt_corpus": False,
            "enable_session": False, "metadata_policy": "historical_static_catalog",
            "trajectory_file": f"{name}.jsonl"}},
        "eval/baselines": {"baselines": {"seed": 0, "item_knn": {"k": 2}}},
        "agent/scoring": {"scoring": {"mode": mode, "hybrid_popularity_weight": 4.0}},
        "eval/segment_thresholds": {"segment_thresholds": {"sparse_max_history": 4}},
        "agent/inference": {"inference": {"mode": "template"}},
    }
    overlay_path = base / f"overlay_{name}.yaml"
    overlay_path.write_text(yaml.safe_dump(overlay, sort_keys=False), encoding="utf-8")
    monkeypatch.setenv("CONFIG_OVERLAY_PATH", str(overlay_path))
    monkeypatch.setattr(sys, "argv", ["run_agent_eval", "--eval-on", "validation"])
    script.main()
    return base / "experiments" / "agent_eval" / "exp_001"


@pytest.mark.parametrize("mode", ["baseline", "hybrid"])
def test_scorer_mode_comes_from_yaml_and_is_recorded(environment, monkeypatch, mode):
    base, paths, items = environment
    exp_dir = _launch(monkeypatch, base, mode, mode=mode)

    config = yaml.safe_load((exp_dir / "config.yaml").read_text(encoding="utf-8"))["config"]
    assert config["scorer"]["mode"] == mode
    assert config["protocol"]["scorer"] == config["scorer"]
    assert config["scorer"]["history_splits"] == ["train"]
    assert config["knn_cache_used"] is False

    rows = [json.loads(s) for s in (exp_dir / "trajectories.jsonl").read_text(encoding="utf-8").splitlines()]
    type1 = [r for r in rows if r["agent"] == "type1"]
    assert type1 and all(r["steps"] and r["tool_calls"] for r in type1)

    if mode == "hybrid":
        train = pd.read_parquet(paths.split_path("train"))
        id2item = {v: k for k, v in items.items()}
        for request in (json.loads(s) for s in (exp_dir / "requests.jsonl").read_text(encoding="utf-8").splitlines()):
            if request.get("user_idx") is None:
                continue
            seen = {id2item[i] for i in train.loc[train.user_idx == request["user_idx"], "item_idx"]}
            for row in rows:
                if row["agent"] == "baseline" and row["request_id"] == request["request_id"]:
                    assert not seen.intersection(row["recommended"])
