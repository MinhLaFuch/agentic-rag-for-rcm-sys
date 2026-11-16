import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from package.data.manifest.verify_manifest import verify_manifest
from package.data.manifest.load_audit_profile import load_audit_profile


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def test_snapshot_is_opt_in_and_does_not_hide_artifact_tampering(tmp_path):
    config = tmp_path / 'configs/data.yaml'
    config.parent.mkdir()
    config.write_bytes(b'current config')
    snapshot = tmp_path / 'historical'
    (snapshot / 'configs').mkdir(parents=True)
    (snapshot / 'configs/data.yaml').write_bytes(b'historical config\r\n')
    artifact = tmp_path / 'data.bin'
    artifact.write_bytes(b'original data')
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({
        'schema_version': 1,
        'config_sha256': {'configs/data.yaml': _hash(b'historical config\r\n')},
        'outputs': [{'path': 'data.bin', 'sha256': _hash(b'original data')}],
    }))
    with pytest.raises(ValueError, match='Manifest hash mismatch'):
        verify_manifest(manifest, project_root=tmp_path)
    assert verify_manifest(manifest, project_root=tmp_path, historical_config_root=snapshot)['status'] == 'match'
    artifact.write_bytes(b'tampered')
    with pytest.raises(ValueError, match='data.bin'):
        verify_manifest(manifest, project_root=tmp_path, historical_config_root=snapshot)


@pytest.fixture
def profile(tmp_path, monkeypatch):
    # Import module explicitly: package imports may expose callable names.
    import importlib
    module = importlib.import_module('package.data.manifest.load_audit_profile')
    overlay = tmp_path / 'overlay.yaml'
    overlay.write_bytes(b'data/split: {}\n')
    splits = tmp_path / 'splits'
    splits.mkdir()
    flags = {'data_protocol': 'temporal_train_core', 'cutoff_1': 10, 'cutoff_2': 20}
    (splits / 'stage_3.manifest.json').write_text(json.dumps({'flags': flags}))
    runtime = {'split': {'data_protocol': 'temporal_train_core', 'temporal_train_core': {
        'train_end_inclusive_ms': 10, 'validation_end_inclusive_ms': 20}}}
    doc = {'version': 1, 'tag': 'audit', 'snapshot_root': 'historical', 'overlay_path': 'overlay.yaml',
           'overlay_sha256': _hash(overlay.read_bytes()), 'required_runtime_configs': {'data/split': runtime}}
    path = tmp_path / 'profile.yaml'
    path.write_text(yaml.safe_dump(doc))
    monkeypatch.setenv('EVAL_BUNDLE_PROFILE', str(path))
    monkeypatch.setenv('CONFIG_OVERLAY_PATH', str(overlay))
    monkeypatch.setattr(module, 'load_config', lambda name: runtime)
    return SimpleNamespace(tag='audit', splits_dir=splits), path, overlay, runtime


def test_profile_checks_tag_overlay_and_runtime(profile, tmp_path):
    paths, path, overlay, runtime = profile
    result = load_audit_profile(paths, project_root=tmp_path)
    assert result['tag'] == 'audit'
    assert result['historical_and_runtime_configs_are_separate']
    overlay.write_bytes(b'changed')
    with pytest.raises(ValueError, match='overlay checksum'):
        load_audit_profile(paths, project_root=tmp_path)


def test_profile_rejects_wrong_protocol_even_if_profile_contract_is_changed(profile, tmp_path):
    paths, path, overlay, runtime = profile
    runtime['split']['data_protocol'] = 'legacy_kcore_before_split'
    # Mutating runtime also mutates this test fixture's expected values only in memory;
    # update the profile to demonstrate stage 3 still independently enforces protocol.
    doc = yaml.safe_load(path.read_text())
    doc['required_runtime_configs']['data/split'] = runtime
    path.write_text(yaml.safe_dump(doc))
    with pytest.raises(ValueError, match='stage 3 protocol'):
        load_audit_profile(paths, project_root=tmp_path)


def test_profile_cannot_apply_to_different_tag(profile, tmp_path):
    paths, *_ = profile
    paths.tag = 'another_bundle'
    with pytest.raises(ValueError, match='version/tag'):
        load_audit_profile(paths, project_root=tmp_path)


def test_without_profile_default_stays_strict(monkeypatch):
    monkeypatch.delenv('EVAL_BUNDLE_PROFILE', raising=False)
    assert load_audit_profile(SimpleNamespace()) is None


def test_committed_snapshot_bytes_match_recorded_hashes():
    from package.config import PROJECT_ROOT
    folder = PROJECT_ROOT / 'configs/historical/multi_domain_v2_audit_20261030'
    recovery = yaml.safe_load((folder / 'recovery.yaml').read_text(encoding='utf-8'))
    assert len(recovery['configs']) == 7
    for record in recovery['configs']:
        assert _hash((folder / record['original_path']).read_bytes()) == record['sha256']
