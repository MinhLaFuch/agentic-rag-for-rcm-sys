import sys

import pytest

from scripts.evaluation import candidate_recall


def test_union_baseline_is_identical_with_hybrid_enabled():
    sources = {'popularity': [1, 2], 'item_cf': [2, 3], 'semantic': [4, 5]}
    baseline, _ = candidate_recall.merge_candidate_unions(sources, 3, hybrid=False)
    extended, times = candidate_recall.merge_candidate_unions({**sources, 'hybrid': [8, 9]}, 3, hybrid=True)
    assert extended['union_rr'] == baseline['union_rr']
    assert extended['union_all'] == baseline['union_all']
    assert extended['union_hybrid_rr'] == [1, 2, 8]
    assert extended['union_hybrid_all'] == [1, 2, 3, 8, 9]
    assert all(t >= 0 for t in times.values())


def test_invalid_manifest_stops_before_loading_splits(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['candidate_recall.py'])
    def invalid(*args, **kwargs):
        raise ValueError('Manifest hash mismatch')
    monkeypatch.setattr(candidate_recall, 'verify_tag_manifest', invalid)
    monkeypatch.setattr(candidate_recall, 'load_splits', lambda *args: pytest.fail('must stop before loading data'))
    with pytest.raises(ValueError, match='Manifest hash mismatch'):
        candidate_recall.main()
