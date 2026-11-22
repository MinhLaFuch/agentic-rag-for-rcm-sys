"""HNSW challenge arm for the held-out validation matrix."""

import numpy as np
import hashlib
import json
from pathlib import Path
from time import perf_counter


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def build_ann_search(store, config):
    import faiss
    kind = config.get('index', 'hnsw_flat')
    warmup = config.get('warmup_queries', 0)
    if type(warmup) is not int or warmup < 0:
        raise ValueError('warmup_queries must be a non-negative integer')
    started = perf_counter()
    rng = np.random.default_rng(config.get('seed', 42))
    index_dir = config.get('index_path')
    source = 'built_in_memory'
    persisted_manifest = None
    if index_dir:
        root = Path(index_dir)
        manifest_path = root / 'manifest.json'
        if not manifest_path.exists():
            raise ValueError(f'Persisted ANN index missing manifest.json: {root}')
        persisted_manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if persisted_manifest.get('status') != 'complete' or persisted_manifest.get('format') != 'faiss_ann_index_v1':
            raise ValueError(f'Invalid persisted ANN manifest: {root}')
        if persisted_manifest.get('index') != kind or persisted_manifest.get('m') != config['m']:
            raise ValueError(f'Persisted ANN index parameters mismatch: expected ({kind}, m={config["m"]})')
        if persisted_manifest.get('num_items') != len(store.item_ids) or persisted_manifest.get('dimension') != store.dimension:
            raise ValueError('Persisted ANN index shape mismatch with VectorStore')
        expected_bid = config.get('expected_embedding_build_id')
        if expected_bid and persisted_manifest.get('embedding_build_id') != expected_bid:
            raise ValueError('Persisted ANN index embedding_build_id mismatch')
        index_file = root / persisted_manifest['index_file']
        if config.get('verify_checksum', True) and _sha256_file(index_file) != persisted_manifest['index_sha256']:
            raise ValueError(f'Persisted ANN index checksum mismatch: {index_file}')
        index = faiss.read_index(str(index_file))
        source = 'persisted'
    else:
        if kind == 'hnsw_flat':
            index = faiss.IndexHNSWFlat(store.dimension, config['m'], faiss.METRIC_INNER_PRODUCT)
        elif kind in ('hnsw_sq8', 'hnsw_fp16'):
            qtype = faiss.ScalarQuantizer.QT_8bit if kind == 'hnsw_sq8' else faiss.ScalarQuantizer.QT_fp16
            index = faiss.IndexHNSWSQ(store.dimension, qtype, config['m'], faiss.METRIC_INNER_PRODUCT)
            size = min(len(store.item_ids), config.get('train_size', 262144))
            sample = np.sort(rng.choice(len(store.item_ids), size=size, replace=False))
            index.train(np.ascontiguousarray(store.embeddings[sample], dtype=np.float32))
        else:
            raise ValueError(f'Unsupported ANN index: {kind}')
        index.add(store.embeddings)
    index.hnsw.efSearch = config['ef_search']
    ids = store.item_ids
    build_seconds = perf_counter() - started
    # Warm the graph with seeded catalog vectors, never validation queries; excluded from latency.
    warm_times = []
    if warmup:
        rows = np.sort(rng.choice(len(ids), size=min(warmup, len(ids)), replace=False))
        queries = np.ascontiguousarray(store.embeddings[rows], dtype=np.float32)
        fetch = min(len(ids), 4 * config.get('warmup_limit', 200))
        for query in queries:
            start = perf_counter()
            index.search(query[None, :], fetch)
            warm_times.append(perf_counter() - start)
    search = filtered_search(index, ids)
    search.build_info = {
        'index': kind, 'source': source, 'index_path': str(Path(index_dir).resolve()) if index_dir else None,
        'm': config['m'], 'ef_search': config['ef_search'], 'build_seconds': build_seconds,
        'warmup_queries': len(warm_times), 'warmup_source': 'seeded random catalog item vectors',
        'warmup_seconds': float(sum(warm_times)),
        'warmup_p50_seconds': float(np.percentile(warm_times, 50)) if warm_times else None,
        'warmup_last_seconds': warm_times[-1] if warm_times else None}
    return search


def filtered_search(index, ids, *, integer_seen=False):
    def search(vector, valid, seen, limit, stats=None):
        fetch = min(len(ids), 4 * limit + len(seen))
        faiss_seconds = filter_seconds = 0.
        calls = fetched = 0
        while True:
            start = perf_counter()
            _, positions = index.search(np.asarray(vector, dtype=np.float32)[None, :], fetch)
            split = perf_counter()
            if integer_seen:
                accepted = [int(i) for i in positions[0] if i >= 0 and valid[i] and int(i) not in seen]
                items = accepted
            else:
                items = [str(ids[i]) for i in positions[0] if i >= 0 and valid[i] and ids[i] not in seen]
            calls += 1
            fetched += len(positions[0])
            faiss_seconds += split - start
            if len(items) >= limit or fetch == len(ids):
                result = [str(ids[i]) for i in items[:limit]] if integer_seen else items[:limit]
                filter_seconds += perf_counter() - split
                if stats is not None:
                    stats.update(faiss_seconds=faiss_seconds, filter_seconds=filter_seconds,
                                 fetch_total=fetched, retries=calls-1)
                return result
            filter_seconds += perf_counter() - split
            fetch = min(len(ids), 2 * fetch)
    return search
