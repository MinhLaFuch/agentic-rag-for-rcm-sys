"""Offline interruption/corruption/publication tests; no model download or real data."""

from contextlib import closing
import json
import sqlite3
from types import SimpleNamespace

import numpy as np
import pytest

from package.embeddings import VectorStore
from package.embeddings.load_vector_artifact import load_vector_artifact
from package.embeddings.read_catalog_text_chunk import read_catalog_text_chunk
from scripts.data_pipeline import build_full_item_embeddings as builder
from scripts.data_pipeline import build_item_embeddings as legacy
from scripts.data_pipeline.pilot_item_embeddings import _texts_for_ids


class _Encoder:
    dimension = 2

    def __init__(self, fail_at=None, reverse=False):
        self.calls = 0
        self.fail_at = fail_at
        self.reverse = reverse

    def encode(self, texts):
        self.calls += 1
        if self.calls == self.fail_at:
            raise KeyboardInterrupt('simulated interruption')
        values = np.array([[1., 1. + len(t) % 7] for t in texts], dtype=np.float32)
        if self.reverse:
            values[:, 0] = -1
        return values / np.linalg.norm(values, axis=1, keepdims=True)


@pytest.fixture
def setup(tmp_path):
    corpus = tmp_path / 'corpus.sqlite'
    with closing(sqlite3.connect(corpus)) as conn, conn:
        conn.executescript('''
            CREATE TABLE items(item_id TEXT PRIMARY KEY, title TEXT, store TEXT, main_category TEXT, domain TEXT);
            CREATE TABLE item_categories(item_id TEXT, category TEXT);
        ''')
        conn.executemany('INSERT INTO items VALUES (?,?,?,?,?)',
                         [(f'D::{i}', f'keyboard {i}', 'store', 'main', 'D') for i in range(7)])
        conn.executemany('INSERT INTO item_categories VALUES (?,?)', [('D::0', 'z'), ('D::0', 'a')])
    config = dict(provider='hash', model='test', revision=None, dimension=2, device='cpu',
                  batch_size=2, chunk_size=3, max_seq_length=256, text_protocol=builder.TEXT_PROTOCOL)
    return corpus, tmp_path / 'work', tmp_path / 'output', config


def _build(setup, **kwargs):
    corpus, work, output, config = setup
    encoder = kwargs.pop('encoder', _Encoder())
    return builder.build_full_embeddings(corpus, work, output, config,
                                         encoder_factory=lambda *a, **k: encoder, **kwargs)


def _close(store):
    store.item_ids._mmap.close()
    store.embeddings._mmap.close()


def test_resume_after_committed_chunk_and_directory_loader(setup, monkeypatch):
    corpus, work, output, config = setup
    with pytest.raises(KeyboardInterrupt):
        _build(setup, encoder=_Encoder(fail_at=4))
    state = json.loads((work / 'checkpoint.json').read_text())
    assert state['count'] == 3
    assert not output.exists()
    result = _build(setup, resume=True)
    assert result['count'] == result['catalog_count'] == 7
    assert result['partial_catalog'] is False
    store = VectorStore.load(output)
    try:
        assert isinstance(store.embeddings, np.memmap)
        assert len(store) == 7
        assert store.id2idx['D::3'] == 3
        with pytest.raises(KeyError):
            store.id2idx['absent']
        assert [str(i) for i in store.item_ids] == [f'D::{i}' for i in range(7)]
        with closing(sqlite3.connect(corpus)) as conn:
            expected = _Encoder().encode([text for _, text in read_catalog_text_chunk(conn, None, 20)])
        np.testing.assert_allclose(store.embeddings, expected)
    finally:
        _close(store)
    monkeypatch.setattr(legacy, 'build_encoder', lambda *a, **k: _Encoder())
    validated, _, meta = legacy.load_validated_embeddings(output, corpus)
    try:
        assert meta['text_protocol'] == builder.TEXT_PROTOCOL
    finally:
        _close(validated)
    encoder = _Encoder()
    _build(setup, encoder=encoder, resume=True)
    assert encoder.calls == 1  # Probe only; completed catalog is never re-encoded.


def test_corrupt_committed_chunk_is_rejected(setup):
    _, work, output, _ = setup
    with pytest.raises(KeyboardInterrupt):
        _build(setup, encoder=_Encoder(fail_at=4))
    with (work / 'chunk_000000.npy').open('ab') as stream:
        stream.write(b'corruption')
    with pytest.raises(ValueError, match='checksum'):
        _build(setup, resume=True)
    assert not output.exists()


@pytest.mark.parametrize('change', ['config', 'source', 'probe'])
def test_resume_rejects_changed_identity_or_probe(setup, change):
    corpus, work, output, config = setup
    with pytest.raises(KeyboardInterrupt):
        _build(setup, encoder=_Encoder(fail_at=4))
    if change == 'config':
        config['chunk_size'] = 4
    elif change == 'source':
        with corpus.open('ab') as stream:
            stream.write(b'changed')
    with pytest.raises(ValueError, match='fingerprint|probe'):
        _build(setup, encoder=_Encoder(reverse=change == 'probe'), resume=True)
    assert not output.exists()


def test_publish_failure_resumes_without_reencoding(setup, monkeypatch):
    _, work, output, _ = setup
    original = builder._atomic_json
    def fail_manifest(path, value):
        if path.name == 'manifest.json':
            raise OSError('disk error')
        return original(path, value)
    monkeypatch.setattr(builder, '_atomic_json', fail_manifest)
    with pytest.raises(OSError, match='disk error'):
        _build(setup)
    assert not output.exists()
    assert (work / 'publish.tmp/vectors.npy').is_file()
    assert json.loads((work / 'checkpoint.json').read_text())['count'] == 7
    monkeypatch.setattr(builder, '_atomic_json', original)
    encoder = _Encoder()
    _build(setup, encoder=encoder, resume=True)
    assert encoder.calls == 1


def test_invalid_encoder_never_publishes(setup):
    encoder = SimpleNamespace(dimension=2, encode=lambda texts: np.zeros((len(texts), 2), dtype=np.float32))
    with pytest.raises(ValueError, match='nonzero'):
        _build(setup, encoder=encoder)
    assert not setup[2].exists()


def test_uncommitted_orphan_chunk_is_replaced_on_resume(setup, monkeypatch):
    _, work, output, _ = setup
    original = builder._atomic_vectors
    monkeypatch.setattr(builder, '_atomic_vectors', lambda *args: (_ for _ in ()).throw(OSError('interrupted write')))
    with pytest.raises(OSError):
        _build(setup)
    assert json.loads((work / 'checkpoint.json').read_text())['count'] == 0
    assert (work / 'chunk_000000.json').is_file()
    monkeypatch.setattr(builder, '_atomic_vectors', original)
    _build(setup, resume=True)
    assert output.is_dir()


def test_text_protocol_matches_pilot_and_chunk_boundaries(setup):
    corpus, *_ = setup
    with closing(sqlite3.connect(corpus)) as conn:
        rows = read_catalog_text_chunk(conn, None, 3)
        next_rows = read_catalog_text_chunk(conn, rows[-1][0], 3)
        pilot = _texts_for_ids(conn, [item_id for item_id, _ in rows + next_rows])
    assert [text for _, text in rows + next_rows] == [row['text'] for row in pilot]
    assert 'Categories: a, z.' in rows[0][1]


def test_published_vectors_tampering_rejected(setup):
    _, _, output, _ = setup
    _build(setup)
    with (output / 'vectors.npy').open('ab') as stream:
        stream.write(b'changed')
    with pytest.raises(ValueError, match='checksum'):
        load_vector_artifact(output)


def test_no_overwrite_and_exclusive_lock(setup):
    _, work, output, _ = setup
    _build(setup)
    with pytest.raises(FileExistsError):
        _build(setup)
    with builder._BuildLock(work / 'other.lock'):
        with pytest.raises(RuntimeError, match='locked'):
            with builder._BuildLock(work / 'other.lock'):
                pass
    assert output.is_dir()
