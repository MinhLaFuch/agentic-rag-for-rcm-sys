"""Bounded real-model resource pilot; never publishes full-catalog embeddings."""

from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import random
import sqlite3
import sys
import threading
import time

# CLI only: initialize PyTorch before project imports load other native libraries.
# Unit tests can still import this module in the lightweight baseline environment.
_TORCH_PREFLIGHT = {"status": "not_run", "seconds": 0.0}
if __name__ == '__main__' and not any(arg in ('--help', '-h') for arg in sys.argv[1:]):
    print('[environment] importing PyTorch before scientific/project imports', flush=True)
    _torch_started = time.perf_counter()
    import torch as _torch
    _TORCH_PREFLIGHT = {"status": "passed", "seconds": time.perf_counter() - _torch_started,
                        "version": _torch.__version__}
    print(f"[environment] PyTorch {_torch.__version__} import OK", flush=True)

import numpy as np
import yaml

from package.config import PROJECT_ROOT, load_config
from package.config.resolve_bundle_paths import resolve_bundle_paths
from package.data.manifest.load_audit_profile import load_audit_profile
from package.recommenders.shared import file_hash
from package.utils import ensure_utf8_stdout
from scripts.data_pipeline.build_item_embeddings import build_encoder
from package.embeddings.format_catalog_text import format_catalog_text


class _MemoryMonitor:
    def __init__(self):
        try:
            import psutil
        except ImportError as exc:
            raise ImportError("Pilot requires psutil; install it in the pilot environment") from exc
        self.process = psutil.Process()
        self.stop_event = threading.Event()
        self.baseline = self.process.memory_info().rss
        self.peak = self.baseline
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _sample(self):
        memory = self.process.memory_info()
        self.peak = max(self.peak, memory.rss, getattr(memory, "peak_wset", 0))

    def _run(self):
        while not self.stop_event.wait(.05):
            self._sample()

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self._sample()
        self.stop_event.set()
        self.thread.join()


def _sample_ids(conn, limit, seed):
    """One streaming ID pass; reserve balanced domain quotas, not the first N IDs."""
    counts = dict(conn.execute("SELECT domain, COUNT(*) FROM items GROUP BY domain"))
    if not counts or any(not isinstance(domain, str) for domain in counts):
        raise ValueError("Pilot requires a nonempty catalog with explicit domains")
    domains = sorted(counts)
    limit = min(limit, sum(counts.values()))
    quotas = dict.fromkeys(domains, 0)
    while sum(quotas.values()) < limit:
        for domain in domains:
            if quotas[domain] < counts[domain] and sum(quotas.values()) < limit:
                quotas[domain] += 1
    reservoirs = {domain: [] for domain in domains}
    seen = dict.fromkeys(domains, 0)
    rng = random.Random(seed)
    cursor = conn.execute("SELECT item_id, domain FROM items ORDER BY item_id")
    try:
        for item_id, domain in cursor:
            seen[domain] += 1
            bucket = reservoirs[domain]
            if len(bucket) < quotas[domain]:
                bucket.append(item_id)
            else:
                position = rng.randrange(seen[domain])
                if position < quotas[domain]:
                    bucket[position] = item_id
    finally:
        cursor.close()
    return sorted(item for bucket in reservoirs.values() for item in bucket), counts, quotas


def _texts_for_ids(conn, item_ids):
    """Sorted categories make text bytes independent of category insertion order."""
    rows = {}
    for start in range(0, len(item_ids), 256):
        chunk = item_ids[start:start + 256]
        marks = ','.join('?' for _ in chunk)
        for item_id, domain, title, store, main in conn.execute(
            f"SELECT item_id, domain, title, store, main_category FROM items WHERE item_id IN ({marks})", chunk
        ):
            rows[item_id] = {"item_id": item_id, "domain": domain, "title": title or "",
                             "store": store or "", "main": main or "", "categories": []}
        for item_id, category in conn.execute(
            f"SELECT item_id, category FROM item_categories WHERE item_id IN ({marks}) ORDER BY item_id, category", chunk
        ):
            rows[item_id]["categories"].append(category)
    result = []
    for item_id in item_ids:
        row = rows[item_id]
        cats = ', '.join(row['categories'])
        text = format_catalog_text(row['title'], row['store'], row['main'], row['categories'])
        result.append({"item_id": item_id, "domain": row['domain'], "text": text,
                       "has_metadata_signal": bool(row['title'] or row['store'] or row['main'] or cats)})
    return result


def _validate_vectors(values, count, dimension):
    vectors = np.asarray(values, dtype=np.float32)
    if vectors.shape != (count, dimension) or not np.isfinite(vectors).all():
        raise ValueError("Encoder returned invalid vector shape or non-finite values")
    norms = np.linalg.norm(vectors, axis=1)
    if np.any(norms <= 0) or not np.allclose(norms, 1., atol=1e-3):
        raise ValueError("Encoder returned zero or unnormalized vectors")
    return vectors


def run_pilot(paths, contract, readiness_path, work_dir, *, limit, batch_size, device, revision=None):
    """Publish a report and a marked partial vector sample, never a production .npz."""
    if not 1 <= limit <= 10_000 or batch_size <= 0:
        raise ValueError("Pilot limit must be 1..10000 and batch size must be positive")
    if contract.get('version') != 1 or contract.get('tag') != paths.tag:
        raise ValueError("Benchmark contract version/tag mismatch")
    spec = contract['pilot']
    if spec['provider'] != 'sentence_transformers' or spec['text_protocol'] != 'title_store_main_category_categories_sorted_v2':
        raise ValueError("Pilot requires the real-model provider and supported text protocol")
    profile = load_audit_profile(paths)
    if profile is None:
        raise ValueError("Pilot requires the verified audit profile/overlay")
    readiness = json.loads(readiness_path.read_text(encoding='utf-8'))
    if readiness.get('tag') != paths.tag or readiness.get('ready_for_evaluation') is not True or readiness.get('blockers'):
        raise ValueError("Readiness report does not attest this bundle as ready")
    if readiness.get('audit_profile', {}).get('sha256') != profile['sha256']:
        raise ValueError("Readiness report and current audit profile differ")
    if readiness.get('protocol', {}).get('recorded') != contract['data_protocol']:
        raise ValueError("Readiness and benchmark data protocols differ")
    work_dir.mkdir(parents=True, exist_ok=False)
    report = {'status': 'started', 'tag': paths.tag, 'purpose': 'resource_pilot_only',
              'partial_catalog': True, 'usable_for_quality_benchmark': False,
              'contract': contract, 'contract_sha256': hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest(),
              'readiness_path': str(readiness_path), 'readiness_sha256': file_hash(readiness_path),
              'audit_profile': profile, 'hardware': {'platform': platform.platform(), 'cpu_count': os.cpu_count()},
              'batch_size': batch_size, 'requested_device': device,
              'torch_preflight': dict(_TORCH_PREFLIGHT)}
    wall_start = time.perf_counter()
    monitor = _MemoryMonitor()
    try:
        with monitor:
            print('[corpus] verifying checksum and selecting bounded domain-balanced sample', flush=True)
            corpus_hash = file_hash(paths.corpus_path)
            attested = [r for r in readiness['artifact_checks']
                        if (PROJECT_ROOT / r['path']).resolve() == paths.corpus_path.resolve() and r['status'] == 'MATCH']
            if not attested or any(r['actual_sha256'] != corpus_hash or r['expected_sha256'] != corpus_hash for r in attested):
                raise ValueError("Current corpus differs from attested P0 corpus")
            sample_start = time.perf_counter()
            with closing(sqlite3.connect(paths.corpus_path.resolve().as_uri() + '?mode=ro', uri=True)) as conn:
                ids, counts, quotas = _sample_ids(conn, limit, contract['seed'])
                rows = _texts_for_ids(conn, ids)
            texts = [row['text'] for row in rows]
            sample_path = work_dir / 'sample.jsonl'
            with sample_path.open('x', encoding='utf-8') as stream:
                for row in rows:
                    stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            report.update(corpus_sha256=corpus_hash, catalog_counts_by_domain=counts, sample_counts_by_domain=quotas,
                          sample_count=len(rows), sample_sha256=file_hash(sample_path),
                          missing_metadata_signal=sum(not row['has_metadata_signal'] for row in rows),
                          sample_seconds=time.perf_counter() - sample_start)
            print(f"[model] loading {spec['model']}; first download is included in model_load_seconds", flush=True)
            started = time.perf_counter()
            encoder = build_encoder('sentence_transformers', spec['model'], revision=revision,
                                    device=device, batch_size=batch_size, max_seq_length=spec['max_seq_length'])
            report['model_load_seconds'] = time.perf_counter() - started
            dimension = spec['expected_dimension']
            if encoder.dimension != dimension:
                raise ValueError('Model dimension differs from benchmark contract')
            report.update(model=spec['model'], revision=encoder.revision, dimension=dimension,
                          actual_device=str(encoder.model.device), max_seq_length=encoder.model.max_seq_length,
                          library_versions={name: version(name) for name in ('sentence-transformers', 'transformers', 'torch', 'numpy', 'psutil')})
            cuda_device = str(encoder.model.device).startswith('cuda')
            if cuda_device:
                import torch
                torch.cuda.reset_peak_memory_stats(encoder.model.device)
                torch.cuda.synchronize(encoder.model.device)
            # Tokenize without truncation to report the actual truncation exposure.
            lengths = []
            for start in range(0, len(texts), batch_size):
                tokens = encoder.model.tokenizer(texts[start:start + batch_size], truncation=False, padding=False)
                lengths.extend(len(tokens) for tokens in tokens['input_ids'])
            report['text_tokens'] = {'p50': float(np.percentile(lengths, 50)), 'p95': float(np.percentile(lengths, 95)),
                                     'max': max(lengths), 'over_max_seq_length': sum(n > encoder.model.max_seq_length for n in lengths)}
            started = time.perf_counter()
            _validate_vectors(encoder.encode(texts[:spec['warmup_items']]), min(len(texts), spec['warmup_items']), dimension)
            report['warmup_seconds'] = time.perf_counter() - started
            runs = []
            vectors = None
            for repeat in range(spec['repeats']):
                started = time.perf_counter()
                vectors = _validate_vectors(encoder.encode(texts), len(texts), dimension)
                seconds = time.perf_counter() - started
                runs.append({'seconds': seconds, 'items_per_second': len(texts) / seconds})
                print(f"[encode] repeat={repeat + 1} items={len(texts)} seconds={seconds:.2f} items/s={len(texts)/seconds:.1f}", flush=True)
            np.save(work_dir / 'pilot_vectors.npy', vectors, allow_pickle=False)
            report['vector_sha256'] = file_hash(work_dir / 'pilot_vectors.npy')
            report['encode_runs'] = runs
            if cuda_device:
                report['gpu_memory'] = {
                    'name': torch.cuda.get_device_name(encoder.model.device),
                    'peak_allocated_gib': torch.cuda.max_memory_allocated(encoder.model.device) / 1024**3,
                    'peak_reserved_gib': torch.cuda.max_memory_reserved(encoder.model.device) / 1024**3,
                }
            rate = float(np.median([run['items_per_second'] for run in runs]))
            report['median_items_per_second'] = rate
            report['full_catalog_encode_seconds_estimate'] = sum(counts.values()) / rate
            report['estimate_scope'] = 'encode-only extrapolation from balanced sample; excludes full extraction, IO, save and index; not a full-build ETA'
            report['full_catalog_float32_vector_gib'] = sum(counts.values()) * dimension * 4 / 1024**3
            report['full_build_memory_gate'] = 'pending: pilot RAM is not an upper bound for current in-memory full builder'
            if file_hash(paths.corpus_path) != corpus_hash:
                raise ValueError('Corpus changed during pilot')
            report['status'] = 'completed'
    except Exception as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        report.update(wall_seconds=time.perf_counter() - wall_start, baseline_rss_gib=monitor.baseline / 1024**3,
                      peak_rss_gib=monitor.peak / 1024**3,
                      memory_scope='RSS monitoring begins after CLI torch preflight; sampled at 50ms; Windows includes process lifetime peak working set')
        (work_dir / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    return report


def main():
    ensure_utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--readiness-report', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True, help='New output directory, outside resource artifacts')
    parser.add_argument('--limit', type=int, default=1000)
    parser.add_argument('--batch-size', type=int, default=64)
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    parser.add_argument('--revision', help='Reuse the immutable revision from a prior pilot report')
    args = parser.parse_args()
    paths = resolve_bundle_paths(tag=args.tag)
    contract_path = PROJECT_ROOT / 'configs/eval/embedding_benchmark_contract.yaml'
    contract = yaml.safe_load(contract_path.read_text(encoding='utf-8'))
    configured_paths = load_config('path/data_paths')['paths']
    protected = [(PROJECT_ROOT / configured_paths[key]).resolve() for key in (
        'raw_dir', 'cleaned_dir', 'filtered_dir', 'mapped_dir', 'splits_dir', 'corpus_dir', 'item_knn_dir')]
    if any(args.work_dir.resolve().is_relative_to(directory) for directory in protected):
        parser.error('Pilot outputs must stay outside resource artifacts')
    result = run_pilot(paths, contract, args.readiness_report, args.work_dir, limit=args.limit,
                       batch_size=args.batch_size, device=args.device, revision=args.revision)
    print(f"[completed] report={args.work_dir / 'report.json'} peak_RSS_GiB={result['peak_rss_gib']:.2f}", flush=True)


if __name__ == '__main__':
    main()
