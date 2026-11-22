"""Tests for Step 5: ranking_eval frozen retrieval-matrix replay, provenance guards, and scorer ablations."""
from __future__ import annotations

from dataclasses import replace
import json
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from scipy import sparse
import yaml

from package.config import get_data_paths
from package.corpus import ItemCorpus
from package.corpus.apply_metadata_policy import apply_metadata_policy
from package.recommenders.shared import file_hash, item_knn_data_hash, mapping_hash
from package.tools.scoring.evidence_scorer import EvidenceScorer
from scripts.evaluation import ranking_eval as script


def _make_env(tmp_path, monkeypatch):
    paths = replace(
        get_data_paths("toy"),
        raw_dir=tmp_path / "raw",
        mapped_dir=tmp_path / "mapped",
        splits_dir=tmp_path / "splits",
        corpus_dir=tmp_path / "corpus",
        cleaned_dir=tmp_path / "cleaned",
    )
    for p in (paths.raw_dir, paths.mapped_dir, paths.splits_dir, paths.cleaned_dir / "Video_Games"):
        p.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"user_id": ["u0"], "parent_asin": ["i0"], "timestamp": [1]}).to_parquet(
        paths.cleaned_path("Video_Games"), index=False
    )
    (paths.raw_dir / "meta_Video_Games.jsonl.gz").write_text("fixture metadata", encoding="utf-8")
    user2id = {"u0": 0, "u1": 1, "u2": 2}
    item2id = {f"Video_Games::i{i}": i for i in range(7)}
    for name, mapping in (("user2id", user2id), ("item2id", item2id)):
        (paths.mapped_dir / f"{name}.json").write_text(json.dumps(mapping), encoding="utf-8")
    train = pd.DataFrame({"user_idx": [0, 0] + [2] * 6, "item_idx": [0, 6] + list(range(6)), "timestamp": [1] * 8})
    val = pd.DataFrame({"user_idx": [0, 1, 2], "item_idx": [2, 3, 6], "timestamp": [2] * 3})
    test = val.assign(timestamp=3)
    for name, df in (("train", train), ("validation", val), ("test", test)):
        df.to_parquet(paths.split_path(name))
    meta = pd.DataFrame({
        "parent_asin": [f"i{i}" for i in range(7)],
        "domain": ["Video_Games"] * 7,
        "first_seen_ts": [1] * 7,
        "title": [f"Game item {i}" for i in range(7)],
    })
    corpus_factory = lambda *a, **k: (ItemCorpus.from_dataframe(meta), meta, 1.0)
    monkeypatch.setattr(script, "get_domains", lambda: ["Video_Games"])
    monkeypatch.setattr(script, "load_mappings", lambda *a: (user2id, item2id))
    monkeypatch.setattr(script, "build_corpus", corpus_factory)
    monkeypatch.setattr("package.config.resolve_bundle_paths.resolve_bundle_paths", lambda **k: paths)
    monkeypatch.setattr(script, "verify_tag_manifest", lambda *a, **k: {
        "status": "match", "manifest_sha256": "abc", "warnings": [], "audit_profile": None
    })
    return paths, user2id, item2id, train, val, meta


def _write_frozen_matrix(matrix_dir, paths, user2id, item2id, train, val, meta):
    matrix_dir.mkdir(parents=True, exist_ok=True)
    corpus = ItemCorpus.from_dataframe(meta)
    policy = apply_metadata_policy(corpus, "historical_static_catalog", as_of_timestamp=int(val.timestamp.min()))
    fit_hash = item_knn_data_hash(train[["user_idx", "item_idx"]])
    id2item = {v: k for k, v in item2id.items()}
    rows = [
        {
            "user_idx": 1, "segment": "cold", "mode": "recency_weighted", "budget": 3,
            "query": {"text": ""}, "seen": [], "targets": [id2item[3]], "seen_target_count": 0,
            "pools": {"bm25": [], "hybrid": [], "fused": [id2item[3], id2item[1], id2item[2]]},
            "source_evidence": [
                {"item_id": id2item[3], "score": 0.05},
                {"item_id": id2item[1], "score": 0.03},
                {"item_id": id2item[2], "score": 0.02},
            ],
            "latency": {"item_cf": 0.0, "bm25": 0.0, "dense": 0.0},
            "no_input": True,
        },
        {
            "user_idx": 0, "segment": "sparse", "mode": "recency_weighted", "budget": 3,
            "query": {"text": "Game item 0"}, "seen": [id2item[0], id2item[6]], "targets": [id2item[2]], "seen_target_count": 0,
            "pools": {
                "bm25": [id2item[2], id2item[1], id2item[4]],
                "hybrid": [id2item[2], id2item[1], id2item[4]],
                "fused": [id2item[2], id2item[1], id2item[4]],
            },
            "source_evidence": [
                {"item_id": id2item[2], "score": 0.06},
                {"item_id": id2item[1], "score": 0.02},
                {"item_id": id2item[4], "score": 0.01},
            ],
            "latency": {"item_cf": 0.01, "bm25": 0.02, "dense": 0.01},
            "no_input": False,
        },
        {
            "user_idx": 2, "segment": "warm", "mode": "recency_weighted", "budget": 3,
            "query": {"text": "Game item 5"},
            "seen": [id2item[i] for i in range(6)], "targets": [id2item[6]], "seen_target_count": 0,
            "pools": {"bm25": [id2item[6]], "hybrid": [id2item[6]], "fused": [id2item[6]]},
            "source_evidence": [{"item_id": id2item[6], "score": 0.05}],
            "latency": {"item_cf": 0.01, "bm25": 0.02, "dense": 0.01},
            "no_input": False,
        },
    ]
    pool_path = matrix_dir / "candidate_sets.jsonl"
    pool_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    cfg = {
        "version": 1,
        "config": {"query_modes": ["recency_weighted"], "budgets": [3], "normalization": "raw"},
        "cohort": {"cold": [1], "sparse": [0], "warm": [2]},
        "provenance": {
            "tag": paths.tag,
            "mapping_hash": mapping_hash(item2id),
            "user_mapping_hash": mapping_hash(user2id),
            "fit_hash": fit_hash,
            "split_hashes": {
                "train": file_hash(paths.split_path("train")),
                "validation": file_hash(paths.split_path("validation")),
            },
            "protocol": {
                "item_knn": {"eval_on": "validation"},
                "metadata_policy": policy,
            },
        },
    }
    cfg_path = matrix_dir / "config.json"
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    frozen_path = matrix_dir / "frozen.json"
    frozen_path.write_text(json.dumps({
        "candidate_sets_sha256": file_hash(pool_path),
        "config_sha256": file_hash(cfg_path),
    }), encoding="utf-8")
    hashes = {name: file_hash(matrix_dir / name) for name in ("config.json", "candidate_sets.jsonl", "frozen.json")}
    (matrix_dir / "artifact_hashes.json").write_text(json.dumps({"status": "complete", "hashes": hashes}), encoding="utf-8")
    return matrix_dir


def _run_ranking(monkeypatch, base, name, matrix_dir, *, scorer_variants="hybrid_w4,evidence_normalized",
                 pools="bm25,hybrid,fused", resume=False, work_dir=None):
    overlay = {
        "eval/ranking_eval": {"ranking_eval": {
            "per_segment": 2, "candidate_budget": 3, "ks": [1, 3],
            "popularity_weights": [1e-6],
            "query_normalization": "raw", "use_prebuilt_corpus": False,
            "batch_size": 1, "progress_every": 1,
        }},
        "eval/baselines": {"baselines": {"item_knn": {"k": 2}}},
        "path/data_paths": {"outputs": {"ranking_eval": str(base / (name + "_output"))}},
    }
    overlay_path = base / f"overlay_{name}.yaml"
    overlay_path.write_text(yaml.safe_dump(overlay, sort_keys=False), encoding="utf-8")
    monkeypatch.setenv("CONFIG_OVERLAY_PATH", str(overlay_path))
    args = [
        "ranking_eval", "--domain", "Video_Games",
        "--work-dir", str(work_dir or (base / name)),
        "--candidates-from", str(matrix_dir),
        "--matrix-mode", "recency_weighted",
        "--matrix-budget", "3",
        "--matrix-pools", pools,
        "--scorer-variants", scorer_variants,
    ]
    if resume:
        args.append("--resume")
    monkeypatch.setattr(sys, "argv", args)
    script.main()
    return base / (name + "_output") / "exp_001"


def test_normalized_blend_prevents_tiny_cf_from_overriding_evidence():
    model = SimpleNamespace(
        scores=np.array([1.0, 10.0, 1.0]),
        num_items=3,
        user_items=sparse.csr_matrix([[1.0, 0.0, 0.0]]),
        similarity=sparse.csr_matrix([[0.0, 0.0, 0.01], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]),
    )
    scorer = EvidenceScorer(model, {1: 1.0, 2: 0.0}, mode="normalized_blend", cf_weight=0.2, popularity_weight=0.5, evidence_weight=1.0)
    scores = scorer.score(0, np.array([2, 1]))
    assert scores[1] > scores[0]


def test_ranking_eval_replays_frozen_matrix_with_multi_scorers_and_guards(tmp_path, monkeypatch):
    paths, user2id, item2id, train, val, meta = _make_env(tmp_path, monkeypatch)
    matrix_dir = _write_frozen_matrix(tmp_path / "matrix_run", paths, user2id, item2id, train, val, meta)
    monkeypatch.setattr(script.SearchTool, "execute", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no retrieval")))

    out = _run_ranking(monkeypatch, tmp_path, "replay1", matrix_dir)
    metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["measurement_scope"] == "fixed_candidate_scoring"
    for pool in ("bm25", "hybrid", "fused"):
        assert set(metrics["ranking"][pool]) == {"baseline", "hybrid_w4", "evidence_normalized"}
    assert metrics["ranking"]["fused"]["hybrid_w4"]["per_segment"]["warm"]["metrics"]["1"]["ndcg@1"] == 1.0
    assert metrics["ranking"]["fused"]["baseline"]["per_segment"]["cold"]["metrics"]["3"]["recall@3"] == 1.0
    assert metrics["ranking"]["fused"]["evidence_normalized"]["per_segment"]["cold"]["metrics"]["1"]["ndcg@1"] == 1.0

    # Changing scorer_variants on resume must be rejected by checkpoint_identity.
    with pytest.raises(ValueError):
        _run_ranking(monkeypatch, tmp_path, "replay1", matrix_dir,
                     scorer_variants="hybrid_w4", resume=True, work_dir=tmp_path / "replay1")

    # Tampering with frozen matrix candidate_sets.jsonl must be rejected.
    (matrix_dir / "candidate_sets.jsonl").write_text(
        (matrix_dir / "candidate_sets.jsonl").read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="checksum mismatch"):
        _run_ranking(monkeypatch, tmp_path, "replay_tampered", matrix_dir)
