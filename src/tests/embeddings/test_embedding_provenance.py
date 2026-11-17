import json
import sqlite3

import numpy as np
import pytest

from scripts.data_pipeline.build_item_embeddings import (
    build_embeddings_for_corpus, load_validated_embeddings, build_encoder,
)


@pytest.fixture
def artifact(tmp_path):
    corpus = tmp_path / 'corpus.sqlite'
    with sqlite3.connect(corpus) as conn:
        conn.executescript("""
            CREATE TABLE items(item_id TEXT, title TEXT, store TEXT, main_category TEXT);
            CREATE TABLE item_categories(item_id TEXT, category TEXT);
            INSERT INTO items VALUES ('D::a', 'quiet keyboard', 'store', 'electronics');
        """)
    path = tmp_path / 'vectors.npz'
    build_embeddings_for_corpus(corpus, path, provider='hash')
    return corpus, path


def test_roundtrip_and_resolved_model(artifact):
    corpus, path = artifact
    store, encoder, meta = load_validated_embeddings(path, corpus)
    assert len(store) == 1
    assert meta['model'] == 'sha256-token-hash-128-v1'
    assert meta['experimental_hash_encoder'] is True
    assert np.isfinite(encoder.encode(['keyboard'])).all()


@pytest.mark.parametrize('change', ['corpus', 'artifact', 'missing_sidecar', 'probe', 'missing_revision'])
def test_rejects_incompatible_artifacts(artifact, change):
    corpus, path = artifact
    meta_path = path.with_suffix('.meta.json')
    if change in ('corpus', 'artifact'):
        with (corpus if change == 'corpus' else path).open('ab') as stream:
            stream.write(b'changed')
    elif change == 'missing_sidecar':
        meta_path.unlink()
    else:
        meta = json.loads(meta_path.read_text())
        if change == 'probe':
            meta['encoder_probe'] = [[0.] * 128]
        else:
            del meta['revision']
        meta_path.write_text(json.dumps(meta))
    with pytest.raises(ValueError):
        load_validated_embeddings(path, corpus)


def test_unknown_provider_is_not_hash():
    with pytest.raises(ValueError, match='Unknown'):
        build_encoder('typo')
