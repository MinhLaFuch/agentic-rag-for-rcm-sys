"""Validate a completed full-build artifact and expose normalized vectors via mmap."""

import hashlib
import json
from pathlib import Path

import numpy as np


def load_vector_artifact(path):
    path = Path(path)
    meta = json.loads((path / 'manifest.json').read_text(encoding='utf-8'))
    if (meta.get('format_version') != 2 or meta.get('status') != 'complete'
            or meta.get('kind') != 'full_catalog_embeddings' or meta.get('partial_catalog') is not False
            or meta.get('count') != meta.get('catalog_count') or meta.get('count', 0) <= 0):
        raise ValueError('Artifact is not a completed full-catalog embedding build')
    for name in ('vectors.npy', 'item_ids.npy'):
        record = meta['files'][name]
        h = hashlib.sha256()
        with (path / name).open('rb') as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                h.update(chunk)
        if h.hexdigest() != record['sha256']:
            raise ValueError(f'Embedding checksum mismatch: {name}')
    vectors = ids = None
    try:
        vectors = np.load(path / 'vectors.npy', mmap_mode='r', allow_pickle=False)
        ids = np.load(path / 'item_ids.npy', mmap_mode='r', allow_pickle=False)
        if vectors.shape != (meta['count'], meta['dimension']) or vectors.dtype != np.float32:
            raise ValueError('Embedding vector shape/dtype mismatch')
        if ids.shape != (meta['count'],) or ids.dtype.kind != 'U':
            raise ValueError('Embedding IDs shape/dtype mismatch')
        previous = None
        for start in range(0, len(ids), 8192):
            group = ids[start:start + 8192]
            values = vectors[start:start + 8192]
            if (not str(group[0]) or (previous is not None and group[0] <= previous)
                    or np.any(group[1:] <= group[:-1])):
                raise ValueError('Embedding IDs must be unique and strictly sorted')
            if not np.isfinite(values).all() or not np.allclose(np.linalg.norm(values, axis=1), 1., atol=1e-3):
                raise ValueError('Embedding vectors must be finite, nonzero and normalized')
            previous = str(group[-1])
        return ids, vectors, meta
    except Exception:
        for array in (ids, vectors):
            if array is not None and hasattr(array, '_mmap'):
                array._mmap.close()
        raise
