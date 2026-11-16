"""Synthetic P0 audit regressions; no real data files are touched."""

import hashlib
import json
import sqlite3
from dataclasses import replace
from contextlib import closing

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from package.config import get_data_paths, get_domains, load_config
from package.corpus import CORPUS_LOGIC_VERSION, get_corpus_schema_fingerprint
from package.recommenders.shared import mapping_hash
from scripts.data_pipeline.audit_bundle import audit_bundle, _contained, _scan_splits


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def bundle(tmp_path):
    original = get_data_paths(tag="audit")
    updates = {name: tmp_path / name for name in (
        "src_root", "config_dir", "raw_dir", "cleaned_dir", "filtered_dir", "mapped_dir",
        "splits_dir", "item_knn_dir", "corpus_dir", "log_dir", "experiments_dir")}
    paths = replace(original, **updates)
    mapping = {"Video_Games::a": 0, "Video_Games::b": 1}
    _write(paths.mapped_dir / "item2id.json", mapping)
    _write(paths.mapped_dir / "user2id.json", {"u": 0})
    paths.filtered_path.parent.mkdir(parents=True)
    paths.filtered_path.write_bytes(b"filtered-data")
    for split, timestamp in zip(("train", "validation", "test"), (1, 2, 3)):
        paths.split_path(split).parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.table({"user_idx": [0], "item_idx": [0], "timestamp": [timestamp]}), paths.split_path(split))
    paths.corpus_path.parent.mkdir(parents=True)
    with closing(sqlite3.connect(paths.corpus_path)) as conn, conn:
        conn.execute("CREATE TABLE items(item_id TEXT, domain TEXT, first_seen_ts INTEGER)")
        conn.executemany("INSERT INTO items VALUES (?, 'Video_Games', 1)", [(key,) for key in mapping])
        conn.execute("CREATE TABLE item_categories(item_id TEXT, category TEXT)")
        conn.execute("CREATE VIRTUAL TABLE items_fts USING fts5(title)")
        conn.execute("CREATE INDEX idx_items_id ON items(item_id)")
        conn.execute("CREATE INDEX idx_items_domain ON items(domain)")
        conn.execute("CREATE INDEX idx_cat_item ON item_categories(item_id)")
    _write(paths.corpus_path.with_suffix('.meta.json'), {
        "format_version": 2, "logic_version": CORPUS_LOGIC_VERSION,
        "schema_fingerprint": get_corpus_schema_fingerprint(), "mapping_hash": mapping_hash(mapping),
        "num_items": 2, "coverage": 1., "num_items_with_first_seen_ts": 2,
        "first_seen_protocol": "minimum_timestamp_per_namespaced_item_in_all_cleaned_interactions_v1",
        "artifact_sha256": _sha(paths.corpus_path),
    })
    stage3_flags = {"data_protocol": load_config("data/split")["split"]["data_protocol"]}
    if stage3_flags["data_protocol"] == "temporal_train_core":
        # Synthetic timestamps intentionally require synthetic cutoffs in this fixture.
        stage3_flags.update(cutoff_1=1, cutoff_2=2)
    stage_paths = [(paths.stage1_manifest_path(d), "clean_domain", []) for d in get_domains()]
    stage_paths += [
        (paths.filtered_path.parent / 'stage_2.manifest.json', 'merge_filter_domains', [paths.filtered_path]),
        (paths.splits_dir / 'stage_3.manifest.json', 'map_split', [paths.mapped_dir / 'item2id.json', paths.mapped_dir / 'user2id.json', *(paths.split_path(s) for s in ('train', 'validation', 'test'))]),
        (paths.corpus_dir / 'stage_4.manifest.json', 'build_artifacts', [paths.corpus_path, paths.corpus_path.with_suffix('.meta.json')]),
    ]
    config = tmp_path / 'configs/config.yaml'
    config.parent.mkdir()
    config.write_text('original')
    for path, stage, outputs in stage_paths:
        _write(path, {"schema_version": 1, "stage": stage, "tag": paths.tag,
                      "flags": stage3_flags if stage == 'map_split' else {"domains": get_domains()},
                      "counts": {"num_users": 1, "num_items": 2, "train_rows": 1, "validation_rows": 1, "test_rows": 1},
                      "outputs": [{"path": p.relative_to(tmp_path).as_posix(), "sha256": _sha(p)} for p in outputs],
                      "config_sha256": {"configs/config.yaml": _sha(config)}})
    return paths, tmp_path, config


def test_full_valid_audit_has_no_blockers(bundle, monkeypatch):
    paths, root, _ = bundle
    # Use a matching runtime contract independent of the developer's current config.
    import scripts.data_pipeline.audit_bundle as module
    original = module.load_config
    def config(name):
        if name == 'data/split':
            return {'split': {'data_protocol': 'legacy_kcore_before_split'}}
        return original(name)
    monkeypatch.setattr(module, 'load_config', config)
    stage3 = paths.splits_dir / 'stage_3.manifest.json'
    doc = json.loads(stage3.read_text())
    doc['flags'] = {'data_protocol': 'legacy_kcore_before_split'}
    _write(stage3, doc)
    report = audit_bundle(paths, root=root, scan_splits=True, scratch_dir=root)
    assert report['ready_for_evaluation'] is True, report['blockers']
    assert report['blockers'] == []
    assert report['corpus']['first_seen_rows'] == 2


def test_config_drift_does_not_become_artifact_failure(bundle):
    paths, root, config = bundle
    config.write_text('changed')
    report = audit_bundle(paths, root=root)
    assert report['config_drift'] == ['configs/config.yaml']
    assert all(row['status'] == 'MATCH' for row in report['artifact_checks'])
    assert report['ready_for_evaluation'] is False
    assert report['split_scan']['status'] == 'not_run'


def test_artifact_tampering_is_not_ignored(bundle):
    paths, root, _ = bundle
    paths.filtered_path.write_bytes(b'changed')
    report = audit_bundle(paths, root=root)
    assert any(row['status'] == 'MISMATCH' for row in report['artifact_checks'])
    assert report['ready_for_evaluation'] is False


def test_missing_chain_is_blocked(bundle):
    paths, root, _ = bundle
    (paths.splits_dir / 'stage_3.manifest.json').unlink()
    report = audit_bundle(paths, root=root)
    assert any('Missing manifest' in blocker for blocker in report['blockers'])


def test_streaming_scan_detects_temporal_and_event_overlap(bundle):
    paths, root, _ = bundle
    good = _scan_splits(paths, 2, 1, root)
    assert good['temporal_order_valid']
    assert good['overlapping_events'] == 0
    pq.write_table(pa.table({'user_idx': [0], 'item_idx': [0], 'timestamp': [1]}), paths.split_path('test'))
    bad = _scan_splits(paths, 2, 1, root)
    assert bad['temporal_order_valid'] is False
    assert bad['overlapping_events'] == 1
    assert not list(root.glob('bundle-split-audit-*'))


def test_streaming_scan_rejects_indices_outside_mapping(bundle):
    paths, root, _ = bundle
    pq.write_table(pa.table({'user_idx': [2], 'item_idx': [0], 'timestamp': [1]}), paths.split_path('train'))
    with pytest.raises(ValueError, match='Out-of-mapping'):
        _scan_splits(paths, 2, 1, root)
    assert not list(root.glob('bundle-split-audit-*'))


@pytest.mark.parametrize('path', ['../escape', '/absolute', 'C:\\absolute'])
def test_manifest_paths_are_contained(tmp_path, path):
    with pytest.raises(ValueError):
        _contained(tmp_path, path)
