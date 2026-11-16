from contextlib import closing
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from scripts.data_pipeline import pilot_item_embeddings as pilot


@pytest.fixture
def corpus(tmp_path):
    import sqlite3
    path = tmp_path / 'corpus.sqlite'
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.executescript('''
            CREATE TABLE items(item_id TEXT PRIMARY KEY, domain TEXT, title TEXT, store TEXT, main_category TEXT);
            CREATE TABLE item_categories(item_id TEXT, category TEXT);
        ''')
        conn.executemany('INSERT INTO items VALUES (?,?,?,?,?)',
                         [(f'{d}::{i}', d, f'keyboard {i}', 'store', 'category') for d in ('A', 'B', 'C') for i in range(12)])
        conn.executemany('INSERT INTO item_categories VALUES (?,?)', [('A::0', 'z'), ('A::0', 'a')])
    return path


def test_sampling_is_seeded_balanced_and_bounded(corpus):
    import sqlite3
    with closing(sqlite3.connect(corpus)) as conn:
        ids, counts, quotas = pilot._sample_ids(conn, 9, 42)
        repeated, _, _ = pilot._sample_ids(conn, 9, 42)
        another, _, _ = pilot._sample_ids(conn, 9, 13)
    assert ids == repeated
    assert ids != another
    assert len(ids) == len(set(ids)) == 9
    assert counts == {'A': 12, 'B': 12, 'C': 12}
    assert quotas == {'A': 3, 'B': 3, 'C': 3}


def test_text_categories_are_sorted(corpus):
    import sqlite3
    with closing(sqlite3.connect(corpus)) as conn:
        row = pilot._texts_for_ids(conn, ['A::0'])[0]
    assert 'Categories: a, z.' in row['text']
    assert row['has_metadata_signal'] is True


@pytest.mark.parametrize('vectors', [np.zeros((2, 3)), np.full((2, 3), np.nan), np.ones((1, 3))])
def test_invalid_vectors_are_rejected(vectors):
    with pytest.raises(ValueError):
        pilot._validate_vectors(vectors, 2, 3)


def test_pilot_writes_partial_artifacts_and_measured_report(corpus, tmp_path, monkeypatch):
    contract = {'version': 1, 'tag': 'audit', 'seed': 42, 'data_protocol': 'temporal_train_core',
                'pilot': {'provider': 'sentence_transformers', 'model': 'fake-model', 'expected_dimension': 3,
                          'max_seq_length': 256, 'warmup_items': 2, 'repeats': 2,
                          'text_protocol': 'title_store_main_category_categories_sorted_v2'}}
    readiness = tmp_path / 'readiness.json'
    digest = hashlib.sha256(corpus.read_bytes()).hexdigest()
    readiness.write_text(json.dumps({'tag': 'audit', 'ready_for_evaluation': True, 'blockers': [],
                                    'audit_profile': {'sha256': 'profile'}, 'protocol': {'recorded': 'temporal_train_core'},
                                    'artifact_checks': [{'path': str(corpus), 'status': 'MATCH',
                                                         'expected_sha256': digest, 'actual_sha256': digest}]}))
    monkeypatch.setattr(pilot, 'load_audit_profile', lambda paths: {'sha256': 'profile'})
    class Monitor:
        baseline = peak = 1024**3
        def __enter__(self): return self
        def __exit__(self, *args): pass
    monkeypatch.setattr(pilot, '_MemoryMonitor', Monitor)
    model = SimpleNamespace(device='cpu', max_seq_length=256,
                            tokenizer=lambda texts, **kwargs: {'input_ids': [[1, 2] for _ in texts]})
    encoder = SimpleNamespace(model=model, dimension=3, revision='a' * 40,
                              encode=lambda texts: np.tile(np.array([[1., 0., 0.]], dtype=np.float32), (len(texts), 1)))
    monkeypatch.setattr(pilot, 'build_encoder', lambda *args, **kwargs: encoder)
    monkeypatch.setattr(pilot, 'version', lambda name: 'test')
    output = tmp_path / 'pilot'
    report = pilot.run_pilot(SimpleNamespace(tag='audit', corpus_path=corpus), contract, readiness, output,
                             limit=9, batch_size=4, device='cpu')
    assert report['status'] == 'completed'
    assert report['sample_count'] == 9
    assert report['usable_for_quality_benchmark'] is False
    assert len(report['encode_runs']) == 2
    assert report['peak_rss_gib'] == 1
    assert report['median_items_per_second'] > 0
    assert (output / 'report.json').is_file()
    assert (output / 'pilot_vectors.npy').is_file()
    assert not list(output.glob('*.npz'))
    assert hashlib.sha256(corpus.read_bytes()).hexdigest() == digest
    with pytest.raises(FileExistsError):
        pilot.run_pilot(SimpleNamespace(tag='audit', corpus_path=corpus), contract, readiness, output,
                        limit=9, batch_size=4, device='cpu')
