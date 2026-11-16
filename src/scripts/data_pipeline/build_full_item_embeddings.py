"""Chunked full-catalog encoding with validated resume and atomic directory publish."""

from __future__ import annotations

import argparse
from contextlib import closing, ExitStack
import hashlib
from importlib.metadata import version, PackageNotFoundError
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import time

# Keep the Windows DLL initialization order that passed both resource pilots.
if __name__ == '__main__' and not any(a in ('-h', '--help') for a in sys.argv[1:]):
    print('[environment] importing PyTorch first', flush=True)
    import torch
    print(f'[environment] PyTorch {torch.__version__} import OK', flush=True)

import numpy as np
import yaml

from package.config import PROJECT_ROOT
from package.config.resolve_bundle_paths import resolve_bundle_paths
from package.data.manifest.load_audit_profile import load_audit_profile
from package.embeddings.format_catalog_text import format_catalog_text
from package.embeddings.read_catalog_text_chunk import read_catalog_text_chunk
from package.embeddings.load_vector_artifact import load_vector_artifact
from package.recommenders.shared import file_hash
from package.utils import ensure_utf8_stdout
from scripts.data_pipeline.build_item_embeddings import build_encoder


TEXT_PROTOCOL = 'title_store_main_category_categories_sorted_v2'
PROBE = 'catalog retrieval encoder compatibility probe'


class _BuildLock:
    """OS advisory lock; automatically released when a killed process exits."""
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        self.stream = self.path.open('a+b')
        if self.path.stat().st_size == 0:
            self.stream.write(b'0')
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            raise RuntimeError(f'Build/output is locked by another process: {self.path}')
        return self

    def __exit__(self, *args):
        try:
            self.stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
        finally:
            self.stream.close()


def _atomic_json(path, value):
    temp = path.with_name(path.name + '.tmp')
    with temp.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def _atomic_vectors(path, values):
    temp = path.with_name(path.name + '.tmp')
    with temp.open('wb') as stream:
        np.save(stream, values, allow_pickle=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def _vectors(values, count, dimension):
    result = np.asarray(values, dtype=np.float32)
    if result.shape != (count, dimension) or not np.isfinite(result).all():
        raise ValueError('Invalid embedding shape or non-finite vectors')
    if not np.allclose(np.linalg.norm(result, axis=1), 1., atol=1e-3):
        raise ValueError('Embedding vectors must be nonzero and normalized')
    return result


def _versions():
    result = {'python': sys.version.split()[0]}
    for name in ('numpy', 'sentence-transformers', 'transformers', 'torch'):
        try:
            result[name] = version(name)
        except PackageNotFoundError:
            result[name] = None
    return result


def _source_hashes():
    import inspect
    return {name: file_hash(inspect.getfile(obj)) for name, obj in (
        ('builder', build_full_embeddings), ('encoder', build_encoder),
        ('text', format_catalog_text), ('reader', read_catalog_text_chunk))}


def _read_committed(work, record, dimension, previous):
    # Paths are derived from sequence number, never trusted from checkpoint strings.
    stem = f"chunk_{record['index']:06d}"
    ids_path, vector_path = work / (stem + '.json'), work / (stem + '.npy')
    if file_hash(ids_path) != record['ids_sha256'] or file_hash(vector_path) != record['vectors_sha256']:
        raise ValueError(f'Committed chunk checksum mismatch: {stem}')
    ids = json.loads(ids_path.read_text(encoding='utf-8'))
    if (not ids or len(ids) != record['count'] or not all(isinstance(i, str) and i for i in ids)
            or any(a >= b for a, b in zip(ids, ids[1:])) or (previous is not None and ids[0] <= previous)
            or ids[-1] != record['last_id']):
        raise ValueError(f'Committed chunk ID order/count mismatch: {stem}')
    values = _vectors(np.load(vector_path, allow_pickle=False), len(ids), dimension)
    return ids, values


def _publish(work, output, state, metadata):
    """Merge chunk files into disk-backed NPY arrays; rename only when complete."""
    stage = work / 'publish.tmp'
    stage.mkdir(exist_ok=True)
    count, dimension = metadata['count'], metadata['dimension']
    vectors = ids_array = None
    try:
        vectors = np.lib.format.open_memmap(stage / 'vectors.npy', mode='w+', dtype=np.float32, shape=(count, dimension))
        ids_array = np.lib.format.open_memmap(stage / 'item_ids.npy', mode='w+', dtype=f"<U{state['max_id_chars']}", shape=(count,))
        offset, previous = 0, None
        for record in state['chunks']:
            ids, values = _read_committed(work, record, dimension, previous)
            end = offset + len(ids)
            vectors[offset:end] = values
            ids_array[offset:end] = ids
            offset, previous = end, ids[-1]
            print(f'[publish] {offset:,}/{count:,} rows', flush=True)
        if offset != count:
            raise ValueError('Cannot publish an incomplete catalog')
        vectors.flush()
        ids_array.flush()
    finally:
        # Windows directory rename requires every memory-mapped handle closed.
        for array in (vectors, ids_array):
            if array is not None:
                array._mmap.close()
    files = {}
    for name in ('vectors.npy', 'item_ids.npy'):
        with (stage / name).open('r+b') as stream:
            os.fsync(stream.fileno())
        files[name] = {'sha256': file_hash(stage / name), 'size_bytes': (stage / name).stat().st_size}
    _atomic_json(stage / 'manifest.json', {**metadata, 'files': files})
    if output.exists():
        raise FileExistsError(f'Output exists; refusing overwrite: {output}')
    stage.rename(output)
    return {**metadata, 'files': files}


def build_full_embeddings(corpus_path, work_dir, output_dir, config, *, evidence=None,
                          resume=False, encoder_factory=None):
    """Encode bounded chunks; checkpoint only fully durable, checksummed chunks."""
    corpus_path, work, output = map(lambda p: Path(p).resolve(), (corpus_path, work_dir, output_dir))
    if work == output or work.is_relative_to(output) or output.is_relative_to(work):
        raise ValueError('Work and output directories must be separate, non-nested paths')
    if config.get('text_protocol') != TEXT_PROTOCOL or config['batch_size'] <= 0 or config['chunk_size'] <= 0:
        raise ValueError('Unsupported text protocol or invalid batch/chunk size')
    if config['provider'] == 'sentence_transformers' and not re.fullmatch('[0-9a-f]{40}', config.get('revision', '')):
        raise ValueError('Full build requires an immutable model revision')
    if work.exists() and not resume:
        raise FileExistsError('Work directory exists; use identical command with --resume')
    if resume and not (work / 'checkpoint.json').is_file():
        raise ValueError('No committed checkpoint to resume')
    if output.exists() and not resume:
        raise FileExistsError('Output exists; refusing overwrite')
    work.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    if work.stat().st_dev != output.parent.stat().st_dev:
        raise ValueError('Work and output must be on the same filesystem for atomic publish')
    with ExitStack() as stack:
        stack.enter_context(_BuildLock(work / 'build.lock'))
        stack.enter_context(_BuildLock(output.parent / ('.' + output.name + '.lock')))
        conn = stack.enter_context(closing(sqlite3.connect(corpus_path.as_uri() + '?mode=ro', uri=True)))
        print('[source] hashing corpus; startup ETA not included in encode ETA', flush=True)
        corpus_hash = file_hash(corpus_path)
        source_stat = corpus_path.stat()
        source_identity = (source_stat.st_size, source_stat.st_mtime_ns)
        if evidence and evidence.get('corpus_sha256') != corpus_hash:
            raise ValueError('Corpus differs from attested source')
        total, unique = conn.execute('SELECT COUNT(*), COUNT(DISTINCT item_id) FROM items').fetchone()
        if total <= 0 or total != unique:
            raise ValueError('Catalog must be nonempty with unique non-null item IDs')
        identity = {'format_version': 1, 'corpus_path': str(corpus_path), 'corpus_sha256': corpus_hash,
                    'catalog_count': total, 'output_dir': str(output), 'config': config,
                    'source_hashes': _source_hashes(), 'environment': _versions(), 'evidence': evidence or {}}
        build_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        checkpoint = work / 'checkpoint.json'
        state = json.loads(checkpoint.read_text(encoding='utf-8')) if resume else {
            'identity': identity, 'build_id': build_id, 'chunks': [], 'count': 0,
            'last_id': None, 'max_id_chars': 0, 'encode_seconds': 0., 'phase': 'encoding'}
        if state.get('identity') != identity or state.get('build_id') != build_id:
            raise ValueError('Resume fingerprint mismatch: source/config/environment/evidence changed')
        print('[model] loading pinned encoder', flush=True)
        factory = encoder_factory or build_encoder
        encoder = factory(config['provider'], config['model'], revision=config['revision'],
                          device=config['device'], batch_size=config['batch_size'], max_seq_length=config['max_seq_length'])
        if config['provider'] == 'sentence_transformers' and getattr(encoder, 'revision', None) != config['revision']:
            raise ValueError('Loaded encoder revision differs from pinned build revision')
        dimension = encoder.dimension
        if dimension != config['dimension']:
            raise ValueError('Encoder dimension differs from build contract')
        probe = _vectors(encoder.encode([PROBE]), 1, dimension)
        if resume:
            saved = np.asarray(state['encoder_probe'], dtype=np.float32)
            if saved.shape != probe.shape or not np.allclose(saved, probe, atol=1e-5, rtol=1e-4):
                raise ValueError('Resume encoder probe mismatch')
        else:
            state['encoder_probe'] = probe.tolist()
            _atomic_json(checkpoint, state)
        previous, count, width = None, 0, 0
        for index, record in enumerate(state['chunks']):
            if record['index'] != index:
                raise ValueError('Checkpoint chunk order mismatch')
            ids, _ = _read_committed(work, record, dimension, previous)
            count += len(ids)
            previous, width = ids[-1], max(width, max(map(len, ids)))
        if (count, previous, width) != (state['count'], state['last_id'], state['max_id_chars']) or count > total:
            raise ValueError('Checkpoint count/boundary mismatch')
        if output.exists():
            ids_map, vectors_map, meta = load_vector_artifact(output)
            ids_map._mmap.close()
            vectors_map._mmap.close()
            if meta.get('build_id') != build_id or count != total:
                raise ValueError('Existing output does not match completed checkpoint')
            state['phase'] = 'published'
            _atomic_json(checkpoint, state)
            print('[complete] existing publication verified', flush=True)
            return meta
        while state['count'] < total:
            rows = read_catalog_text_chunk(conn, state['last_id'], config['chunk_size'])
            if not rows:
                raise ValueError('Catalog exhausted before expected row count')
            ids = [row[0] for row in rows]
            if any(not isinstance(i, str) or not i for i in ids):
                raise ValueError('Catalog IDs must be nonempty strings')
            texts = [row[1] for row in rows]
            started = time.perf_counter()
            pieces = []
            for start in range(0, len(texts), config['batch_size']):
                group = texts[start:start + config['batch_size']]
                pieces.append(_vectors(encoder.encode(group), len(group), dimension))
            values = np.concatenate(pieces)
            seconds = time.perf_counter() - started
            current_stat = corpus_path.stat()
            if (current_stat.st_size, current_stat.st_mtime_ns) != source_identity:
                raise ValueError('Corpus changed during build')
            index = len(state['chunks'])
            stem = f'chunk_{index:06d}'
            ids_path, vector_path = work / (stem + '.json'), work / (stem + '.npy')
            _atomic_json(ids_path, ids)
            _atomic_vectors(vector_path, values)
            state['chunks'].append({'index': index, 'count': len(ids), 'last_id': ids[-1],
                                    'ids_sha256': file_hash(ids_path), 'vectors_sha256': file_hash(vector_path),
                                    'text_sha256': hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()})
            state.update(count=state['count'] + len(ids), last_id=ids[-1],
                         max_id_chars=max(state['max_id_chars'], max(map(len, ids))),
                         encode_seconds=state['encode_seconds'] + seconds)
            if state['count'] > total:
                raise ValueError('Encoded row count exceeds catalog')
            _atomic_json(checkpoint, state)
            rate = state['count'] / state['encode_seconds'] if state['encode_seconds'] else 0.
            eta = (total - state['count']) / rate if rate else 0.
            print(f"[encode] {state['count']:,}/{total:,} ({state['count']/total:.1%}) {rate:.1f} items/s encode_ETA={eta/3600:.2f}h", flush=True)
        if read_catalog_text_chunk(conn, state['last_id'], 1):
            raise ValueError('Catalog changed or count/order mismatch')
        if file_hash(corpus_path) != corpus_hash:
            raise ValueError('Corpus changed before publication')
        if _source_hashes() != identity['source_hashes'] or _versions() != identity['environment']:
            raise ValueError('Builder source or environment changed during build')
        if evidence:
            for path, expected_hash in evidence.get('mapping_files', {}).items():
                if file_hash(path) != expected_hash:
                    raise ValueError(f'Attested input changed during build: {path}')
            profile = evidence.get('audit_profile', {})
            for path_key, hash_key in (('path', 'sha256'), ('overlay_path', 'overlay_sha256')):
                if profile and file_hash(profile[path_key]) != profile[hash_key]:
                    raise ValueError('Audit profile/overlay changed during build')
        state['phase'] = 'publishing'
        _atomic_json(checkpoint, state)
        metadata = {'format_version': 2, 'status': 'complete', 'kind': 'full_catalog_embeddings',
                    'partial_catalog': False, 'count': total, 'catalog_count': total, 'dimension': dimension,
                    'build_id': build_id, 'identity': identity, 'provider': config['provider'],
                    'model': config['model'], 'revision': config['revision'], 'device': config['device'],
                    'max_seq_length': config['max_seq_length'], 'text_protocol': TEXT_PROTOCOL,
                    'encoder_probe': probe.tolist(), 'corpus_sha256': corpus_hash,
                    'library_versions': identity['environment'], 'encode_seconds': state['encode_seconds']}
        meta = _publish(work, output, state, metadata)
        state['phase'] = 'published'
        _atomic_json(checkpoint, state)
        print(f'[complete] {output}', flush=True)
        return meta


def main():
    ensure_utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--readiness-report', required=True, type=Path)
    parser.add_argument('--pilot-report', required=True, type=Path)
    parser.add_argument('--work-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--chunk-size', type=int, default=4096)
    parser.add_argument('--batch-size', type=int, default=64)
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    paths = resolve_bundle_paths(tag=args.tag)
    profile = load_audit_profile(paths)
    readiness = json.loads(args.readiness_report.read_text(encoding='utf-8'))
    pilot = json.loads(args.pilot_report.read_text(encoding='utf-8'))
    contract = yaml.safe_load((PROJECT_ROOT / 'configs/eval/embedding_benchmark_contract.yaml').read_text(encoding='utf-8'))
    if not profile or not readiness.get('ready_for_evaluation') or readiness.get('blockers') or readiness.get('tag') != paths.tag:
        raise ValueError('A passing P0 report and active audit profile are required')
    if readiness.get('audit_profile', {}).get('sha256') != profile['sha256'] or pilot.get('audit_profile', {}).get('sha256') != profile['sha256']:
        raise ValueError('Readiness/pilot/profile identity mismatch')
    if (pilot.get('status') != 'completed' or pilot.get('tag') != paths.tag or pilot.get('contract') != contract
            or pilot.get('sample_count', 0) < 10000 or pilot.get('actual_device', '').split(':')[0] != args.device
            or pilot.get('batch_size') != args.batch_size):
        raise ValueError('Require a matching completed 10k pilot for this contract/device/batch')
    if contract['tag'] != paths.tag or readiness['protocol']['recorded'] != contract['data_protocol']:
        raise ValueError('Benchmark contract/P0 bundle protocol mismatch')
    spec = contract['pilot']
    config = {'provider': 'sentence_transformers', 'model': spec['model'], 'revision': pilot['revision'],
              'dimension': spec['expected_dimension'], 'max_seq_length': spec['max_seq_length'],
              'text_protocol': spec['text_protocol'], 'batch_size': args.batch_size,
              'chunk_size': args.chunk_size, 'device': args.device}
    if (pilot.get('model'), pilot.get('dimension'), pilot.get('max_seq_length')) != (config['model'], config['dimension'], config['max_seq_length']):
        raise ValueError('Pilot encoder settings differ from contract')
    corpus_meta = paths.corpus_path.with_suffix('.meta.json')
    evidence = {'tag': paths.tag, 'audit_profile': profile, 'readiness_sha256': file_hash(args.readiness_report),
                'pilot_sha256': file_hash(args.pilot_report), 'corpus_sha256': pilot['corpus_sha256'],
                'mapping_files': {}, 'contract': contract}
    for path in (paths.mapped_dir / 'item2id.json', paths.mapped_dir / 'user2id.json', corpus_meta):
        actual = file_hash(path)
        records = [r for r in readiness['artifact_checks'] if (PROJECT_ROOT / r['path']).resolve() == path.resolve()]
        if not records or any(r['status'] != 'MATCH' or r['actual_sha256'] != actual or r['expected_sha256'] != actual for r in records):
            raise ValueError(f'Current input differs from attested P0 artifact: {path}')
        evidence['mapping_files'][str(path.resolve())] = actual
    build_full_embeddings(paths.corpus_path, args.work_dir, args.output_dir, config,
                          evidence=evidence, resume=args.resume)


if __name__ == '__main__':
    main()
