"""Paired retrieval matrix and RankTool replay over checksummed frozen pools."""

import hashlib
import itertools
import json
import math
from pathlib import Path
import time
import shutil
from contextlib import nullcontext
from package.corpus.item_corpus import offline_select_budget

import numpy as np
import yaml

from package.tools import RankTool
from package.tools.retrieval.history_query_retriever import HistoryQueryRetriever
from package.tools.retrieval.fuse_candidates import fuse_candidates
from package.tools.retrieval.eligible_catalog_ids import eligible_catalog_ids
from package.tools.retrieval.build_history_query import build_history_query
from package.tools.scoring.baseline_scorer import BaselineScorer
from package.tools.scoring.evidence_scorer import EvidenceScorer
from package.recommenders.shared import file_hash
from package.tools import get_tool_limits


def _validate(config):
    if config.get('version') != 1 or not config['query_modes'] or len(set(config['query_modes'])) != len(config['query_modes']):
        raise ValueError('Invalid matrix version/query modes')
    if (not config.get('ann_validation') and not config.get('final_test_frozen') and 'latest_title' not in config['query_modes']) or set(config['query_modes']) - {'latest_title', 'multi_history', 'recency_weighted'}:
        raise ValueError('Matrix requires latest_title baseline and supported history-only modes')
    for key in ('budgets', 'rank_ks'):
        if not config[key] or any(type(n) is not int or n <= 0 for n in config[key]) or len(set(config[key])) != len(config[key]):
            raise ValueError(f'Invalid {key}')
    if max(config['budgets']) > get_tool_limits().max_candidates or max(config['rank_ks']) > min(config['budgets']):
        raise ValueError('Budgets exceed tool limit or ranking K exceeds smallest frozen pool budget')
    if config['bootstrap_samples'] <= 0 or config['max_history_items'] <= 0 or not 0 < config['recency_decay'] <= 1:
        raise ValueError('Invalid bootstrap/history settings')
    if set(config['scoring']['modes']) - {'baseline', 'cf_ties', 'additive_ablation'} or 'baseline' not in config['scoring']['modes']:
        raise ValueError('Scoring requires baseline and explicit supported ablations')
    cold = config.get('cold_start', {})
    if cold.get('fallback_source') not in (None, 'popularity') or not isinstance(cold.get('include_in_fused', True), bool):
        raise ValueError('Invalid cold_start fallback configuration')
    f = config['fusion']
    known_sources = ['popularity', 'item_cf', 'bm25', 'dense']
    if 'domain_cat_pop' in (f.get('quotas') or {}) or 'domain_cat_pop' in (f.get('weights') or {}):
        known_sources.append('domain_cat_pop')
    fuse_candidates({s: [] for s in known_sources}, budget=1, **f)
    for name in ('min_recall_delta_ci_low', 'max_p95_seconds', 'max_segment_recall_regression'):
        value = config['gates'][name]
        if value is not None and (not isinstance(value, (int, float)) or not math.isfinite(value)):
            raise ValueError('Gates must be finite or null')
    if config.get('ann_validation') and config.get('dense_ann'):
        raise ValueError('Configure either ann_validation or dense_ann, not both')
    if config.get('bm25_sql_seconds') is not None:
        val = config['bm25_sql_seconds']
        if not isinstance(val, (int, float)) or not math.isfinite(val) or val <= 0:
            raise ValueError('bm25_sql_seconds must be a positive finite number')


def _quality(candidates, targets, k):
    gt, top = set(targets), candidates[:k]
    if not gt:
        return {'recall': None, 'hit_rate': None, 'ndcg': None, 'mrr': None}
    hit = [int(i in gt) for i in top]
    dcg = sum(value / math.log2(rank + 2) for rank, value in enumerate(hit))
    ideal = sum(1 / math.log2(rank + 2) for rank in range(min(k, len(gt))))
    return {'recall': sum(hit) / len(gt), 'hit_rate': float(any(hit)), 'ndcg': dcg / ideal,
            'mrr': next((1 / (rank + 1) for rank, value in enumerate(hit) if value), 0.)}


def _paired(left, right, seed, samples):
    keys = sorted(set(left) & set(right))
    if set(left) != set(right):
        raise ValueError('Paired comparison cohort mismatch')
    if not keys:
        return {'users': 0, 'mean_delta': None, 'ci95': None}
    delta = np.array([left[u] - right[u] for u in keys])
    rng = np.random.default_rng(seed)
    # One replicate at a time bounds RAM for population-sized cohorts.
    means = [float(delta[rng.integers(len(delta), size=len(delta))].mean()) for _ in range(samples)]
    return {'users': len(keys), 'mean_delta': float(delta.mean()), 'ci95': np.percentile(means, [2.5, 97.5]).tolist()}


def _latency(values):
    return {'n': len(values), 'p50_seconds': float(np.percentile(values, 50)) if values else None,
            'p95_seconds': float(np.percentile(values, 95)) if values else None}


def _gate(config, comparison, segment_comparisons, latency):
    required = ('min_recall_delta_ci_low', 'max_p95_seconds', 'max_segment_recall_regression')
    if any(config[key] is None for key in required):
        return {'status': 'not_set', 'passed': None, 'reason': 'Set all thresholds before acceptance evaluation'}
    if not comparison or comparison['ci95'] is None or not latency or latency['p95_seconds'] is None or not segment_comparisons:
        return {'status': 'insufficient_data', 'passed': None}
    passed = (comparison['ci95'][0] >= config['min_recall_delta_ci_low']
              and latency['p95_seconds'] <= config['max_p95_seconds']
              and all(c['ci95'] is not None and c['ci95'][0] >= -config['max_segment_recall_regression'] for c in segment_comparisons))
    return {'status': 'pass' if passed else 'fail', 'passed': bool(passed)}


def run_matrix(*, output, config_path, sampled, recent, fit_events, item_text, id2item,
               user2id, item2id, targets, cutoff, knn, item_cf, search, vector_store, encoder,
               corpus, provenance, popularity_order=None, trace_ann=False):
    config = yaml.safe_load(Path(config_path).read_text(encoding='utf-8'))
    _validate(config)
    ann = config.get('ann_validation')
    dense_ann = config.get('dense_ann')
    snapshot = None
    if trace_ann:
        if not ann:
            raise ValueError('--trace-ann requires ann_validation')
        import psutil
        import faiss
        process = psutil.Process()
        config['diagnostic_only'] = True
        trace_rows = []
        def snapshot():
            info = process.memory_info()
            return {'rss_bytes': info.rss, 'available_bytes': psutil.virtual_memory().available,
                    'page_faults': getattr(info, 'num_page_faults', None)}
    if ann and (config['query_modes'] != ['recency_weighted'] or config['budgets'] != [200]
                or config['rank_ks'] != [10] or config['scoring']['modes'] != ['baseline']
                or provenance['protocol']['item_knn']['eval_on'] != 'validation'):
        raise ValueError('ANN challenge requires the paired validation protocol')
    eval_on = provenance.get('protocol', {}).get('item_knn', {}).get('eval_on', 'validation')
    if eval_on == 'test' and not config.get('final_test_frozen'):
        raise ValueError('Held-out test matrix requires final_test_frozen: true in the frozen config')
    if config.get('final_test_frozen') and ann:
        raise ValueError('final_test_frozen cannot be combined with ann_validation')
    if provenance.get('protocol', {}).get('metadata_policy', {}).get('name') == 'no_filter':
        raise ValueError('Acceptance matrix requires an explicit temporal metadata policy')
    if vector_store is None or encoder is None:
        raise ValueError('Matrix requires validated real embedding artifact')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    # Eligibility is read from the already-applied metadata policy, before dense Top-K.
    eligible = eligible_catalog_ids(corpus, vector_store.item_ids)
    bm25_index = None
    bm25_manifest = None
    if config.get('bm25_index_path'):
        from package.embeddings.sparse_bm25_index import SparseBM25Index
        bm25_index = SparseBM25Index.load(config['bm25_index_path'])
        bm25_manifest = bm25_index.manifest
        print(f"[matrix] loaded SparseBM25Index: {len(bm25_index):,} items, vocab={bm25_manifest.get('vocab_size'):,}", flush=True)
    retriever = HistoryQueryRetriever(search, vector_store, encoder, eligible_ids=eligible,
                                       block_rows=config['dense_block_rows'], bm25_index=bm25_index)
    max_budget = max(config['budgets'])
    ann_search = None
    if ann or dense_ann:
        from scripts.evaluation.ann_validation import build_ann_search
        ann_cfg = dict(ann or dense_ann)
        emb_bid = (provenance.get('embeddings') or {}).get('build_id')
        if emb_bid and 'expected_embedding_build_id' not in ann_cfg:
            ann_cfg['expected_embedding_build_id'] = emb_bid
        ann_search = build_ann_search(vector_store, ann_cfg)
    if popularity_order is None:
        popularity_order = []
    popularity_order = [id2item[int(i)] if isinstance(i, (int, np.integer)) else str(i)
                        for i in popularity_order]
    use_domain_cat_pop = (
        'domain_cat_pop' in (config['fusion'].get('quotas') or {})
        or 'domain_cat_pop' in (config['fusion'].get('weights') or {})
    )
    domain_cat_pop = None
    if use_domain_cat_pop:
        from package.tools.retrieval.domain_category_popularity import DomainCategoryPopularity
        dcp_started = time.perf_counter()
        domain_cat_pop = DomainCategoryPopularity.from_corpus(corpus, popularity_order, eligible)
        print(f'[matrix] built DomainCategoryPopularity ({len(domain_cat_pop.domain_buckets)} domains, '
              f'{len(domain_cat_pop.category_buckets)} categories) in {time.perf_counter()-dcp_started:.1f}s', flush=True)
    # Same target denominator for retrieval/ranking here: novel eligible-or-ineligible target
    # items. Catalog misses remain misses, while seen target repeats are reported separately.
    def user_cutoff(user):
        if isinstance(cutoff, dict):
            return cutoff.get(user)
        return cutoff

    manifest = {'version': 1, 'config': config, 'provenance': provenance, 'cutoff': cutoff,
                'cutoff_policy': 'per-user cutoff when supplied; fit history is otherwise pre-target',
                'cohort': sampled, 'target_policy': 'novel targets; targets never used for query or fusion',
                'timing': 'serial per-user wall time, includes query encode; excludes input loading/model warmup',
                'quality_scope': ('final held-out test (frozen validation config; fit=train+validation); '
                                  'cold with no history has no semantic query'
                                  if eval_on == 'test'
                                  else 'validation history proxy; cold with no history has no semantic query')}
    if ann_search is not None:
        if ann:
            manifest['ann_timing'] = ('two-pass: every user runs history/CF/BM25/encode/ANN in a timed runtime pass '
                                      'before any exact dense reference scan; ann_search excludes encode/index build')
        else:
            manifest['ann_timing'] = ('single-pass dense_ann: validated ANN index serves dense directly; '
                                      'excludes index build/warmup')
        manifest['ann_build'] = getattr(ann_search, 'build_info', None)
    if bm25_manifest is not None:
        manifest['bm25_index'] = {
            'path': str(Path(config['bm25_index_path']).resolve()),
            'format': bm25_manifest.get('format'),
            'vocab_size': bm25_manifest.get('vocab_size'),
            'nnz': bm25_manifest.get('nnz'),
            'corpus_sha256': bm25_manifest.get('corpus_sha256'),
            'min_df': bm25_manifest.get('min_df'),
        }
    (output / 'config.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    # Freeze candidate artifacts completely BEFORE RankTool replay. Hash them before/after replay.
    pool_path = output / 'candidate_sets.jsonl'
    # ANN mode defers the exact catalog scan: interleaving it with timed ANN queries evicts the
    # HNSW pages from RAM and measures memory contention instead of runtime search latency.
    two_pass = bool(ann)
    use_ann_as_dense = bool(dense_ann)
    deferred = []

    def freeze(stream, job):
        u, segment, mode, seen, retrieved = job['user'], job['segment'], job['mode'], job['seen'], job['retrieved']
        reference_started = time.perf_counter()
        if two_pass:
            retriever.complete_exact(retrieved, seen=seen, limit=max_budget, rrf_k=config['fusion']['rrf_k'],
                                     memory_snapshot=snapshot)
        reference_seconds = time.perf_counter() - reference_started
        if trace_ann and 'ann_trace' in retrieved:
            trace_rows.append(dict(sequence=len(trace_rows)+1, user_idx=u, segment=segment, **retrieved['ann_trace']))
        popularity = [item for item in popularity_order if item not in seen and item in eligible]
        cf = job['cf']
        sources = {'popularity': popularity, 'item_cf': cf, 'bm25': retrieved['bm25'], 'dense': retrieved['dense'], 'hybrid': retrieved['hybrid']}
        fusion_sources = ('popularity', 'item_cf', 'bm25', 'dense')
        if domain_cat_pop is not None:
            sources['domain_cat_pop'] = domain_cat_pop.recommend(seen, limit=max_budget)
            fusion_sources = ('popularity', 'domain_cat_pop', 'item_cf', 'bm25', 'dense')
        if not config.get('cold_start', {}).get('include_in_fused', True):
            fusion_sources = tuple(s for s in fusion_sources if s != 'popularity')
        all_attribution = fuse_candidates({s: sources[s] for s in fusion_sources},
            budget=max_budget * 3, excluded=seen, **config['fusion'])
        runtime_seconds = job['runtime_seconds'] + job['cf_seconds'] + job['history_seconds']
        retrieve_seconds = runtime_seconds + reference_seconds
        for budget in sorted(config['budgets']):
            fusion_started = time.perf_counter()
            attributed = fuse_candidates({s: sources[s] for s in fusion_sources},
                budget=budget, excluded=seen, **config['fusion'])
            fusion_seconds = time.perf_counter() - fusion_started
            pools = {s: ids[:budget] for s, ids in sources.items()}
            pools['fused'] = [r['item_id'] for r in attributed]
            latency = {**retrieved['latency'], 'item_cf': job['cf_seconds'],
                       'history_metadata': job['history_seconds'],
                       'retrieval_total': retrieve_seconds + fusion_seconds, 'fusion': fusion_seconds}
            if ann:
                ann_sources = {s: sources[s] for s in fusion_sources}
                ann_sources['dense'] = retrieved.get('ann_dense', [])
                pools['ann_dense'] = ann_sources['dense'][:budget]
                ann_fusion_started = time.perf_counter()
                pools['ann_fused'] = [r['item_id'] for r in fuse_candidates(
                    ann_sources, budget=budget, excluded=seen, **config['fusion'])]
                # Runtime-like path: history, CF, BM25, encode, ANN and fusion; no exact scan.
                latency['ann_retrieval_total'] = runtime_seconds + time.perf_counter() - ann_fusion_started
            gt = [id2item[i] for i in sorted(targets[u]) if id2item[i] not in seen]
            ineligible_targets = sum(1 for item in gt if item not in eligible)
            overlap = {f'{a}/{b}': {'intersection': len(set(sources[a][:budget]) & set(sources[b][:budget])),
                'jaccard': len(set(sources[a][:budget]) & set(sources[b][:budget])) / max(1, len(set(sources[a][:budget]) | set(sources[b][:budget])))}
                for a, b in itertools.combinations(sources, 2)}
            stream.write(json.dumps({'user_idx': u, 'segment': segment, 'mode': mode, 'budget': budget,
                'query': retrieved['query'], 'seen': sorted(seen), 'targets': gt,
                'seen_target_count': len(targets[u]) - len(gt),
                'ineligible_target_count': ineligible_targets, 'pools': pools,
                'fusion_attribution': attributed, 'overlap': overlap, 'no_input': retrieved['no_input'],
                'source_evidence': all_attribution, 'fallback_used': job['fallback_used'],
                'latency': latency, 'errors': retrieved.get('errors', {})}, ensure_ascii=False) + '\n')

    try:
        with pool_path.open('x', encoding='utf-8') as stream:
            for segment, users in sampled.items():
                for u in users:
                    seen = {id2item[i] for i in recent.get(u, [])}
                    fallback_used = not recent.get(u) and config.get('cold_start', {}).get('fallback_source') == 'popularity'
                    history_started = time.perf_counter()
                    # Select by the same cutoff/order/dedup semantics as runtime before
                    # asking SQLite for titles. No target or category lookup is needed.
                    selection = build_history_query(fit_events.get(u, []), cutoff=user_cutoff(u),
                        mode='multi_history', max_items=config['max_history_items'])
                    events = [{'item_id': e['item_id'], 'timestamp': e['timestamp']}
                              for e in selection['components']]
                    metadata = item_text([e['item_id'] for e in events])
                    history = [{**e, 'title': metadata.get(e['item_id'], ('', ''))[0]} for e in events]
                    history_seconds = time.perf_counter() - history_started
                    cf_started = time.perf_counter()
                    seeds = [id2item[i] for i in recent.get(u, [])[:config['max_history_items']]]
                    cf = []
                    if seeds:
                        response = item_cf(items=seeds, top_k=min(max_budget + len(seen), get_tool_limits().max_candidates))
                        item_cf.logger.records.clear()
                        if not response.ok:
                            raise RuntimeError(f'CF retrieval error for user {u}')
                        cf = [r['item_id'] for r in response.data['candidates'] if r['item_id'] not in seen and r['item_id'] in eligible]
                    cf_seconds = time.perf_counter() - cf_started
                    for mode in config['query_modes']:
                        started = time.perf_counter()
                        seconds = ann.get('bm25_sql_seconds') if ann else config.get('bm25_sql_seconds')
                        budget_label = seconds or 'default'
                        try:
                            with offline_select_budget(seconds) if seconds is not None else nullcontext():
                                retrieved = retriever.retrieve(history, seen=seen, limit=max_budget, cutoff=user_cutoff(u),
                                    mode=mode, max_items=config['max_history_items'], decay=config['recency_decay'],
                                    normalization=config['normalization'], rrf_k=config['fusion']['rrf_k'], ann_search=ann_search,
                                    memory_snapshot=snapshot, exact_dense=not two_pass and not use_ann_as_dense,
                                    use_ann_as_dense=use_ann_as_dense)
                        except RuntimeError as exc:
                            raise RuntimeError(f'retrieval failed: user={u}, segment={segment}, mode={mode}, '
                                               f'sql_budget={budget_label}: {exc}') from exc
                        job = {'user': u, 'segment': segment, 'mode': mode, 'seen': seen, 'cf': cf,
                               'retrieved': retrieved, 'fallback_used': fallback_used,
                               'runtime_seconds': time.perf_counter() - started,
                               'cf_seconds': cf_seconds, 'history_seconds': history_seconds}
                        if two_pass:
                            deferred.append(job)
                        else:
                            freeze(stream, job)
                    phase = 'timed' if two_pass else 'frozen'
                    print(f'[matrix] {phase} user={u} segment={segment}', flush=True)
            for job in deferred:
                freeze(stream, job)
                reference_user, reference_segment = job['user'], job['segment']
                print(f'[matrix] exact reference user={reference_user} segment={reference_segment}', flush=True)
    except Exception as exc:
        (output / 'FAILED.json').write_text(json.dumps({'status': 'failed', 'error': repr(exc)}), encoding='utf-8')
        raise
    pool_hash = file_hash(pool_path)
    if trace_ann:
        first = trace_rows[0]['ann_seconds'] if trace_rows else None
        summary = dict(first_ann_seconds=first, subsequent_ann=_latency([r['ann_seconds'] for r in trace_rows[1:]]),
                       timed_queries=len(trace_rows), faiss_threads=faiss.omp_get_max_threads(),
                       explicit_warmup_queries=0, phase_order='all timed ANN queries before exact reference')
        (output/'ann_trace.json').write_text(json.dumps(dict(summary=summary, rows=trace_rows), indent=2), encoding='utf-8')
    (output / 'frozen.json').write_text(json.dumps({'candidate_sets_sha256': pool_hash, 'config_sha256': file_hash(output / 'config.json')}), encoding='utf-8')
    return replay_matrix(output, knn=knn, user2id=user2id, item2id=item2id, corpus=corpus)


def replay_frozen_matrix(source, output, *, provenance, knn, user2id, item2id, corpus):
    """Verify provenance and copy frozen inputs into a new rank-only output."""
    source, output = Path(source), Path(output)
    completion = json.loads((source / 'artifact_hashes.json').read_text())
    if completion.get('status') != 'complete':
        raise ValueError('Only completed matrix runs may be replayed')
    for name in ('config.json', 'candidate_sets.jsonl', 'frozen.json'):
        if file_hash(source / name) != completion['hashes'][name]:
            raise ValueError('Frozen matrix checksum mismatch')
    saved = json.loads((source / 'config.json').read_text())['provenance']
    if saved != provenance:
        raise ValueError('Frozen matrix/model/data provenance differs from current evaluation')
    output.mkdir(parents=True, exist_ok=False)
    for name in ('config.json', 'candidate_sets.jsonl', 'frozen.json'):
        shutil.copyfile(source / name, output / name)
    return replay_matrix(output, knn=knn, user2id=user2id, item2id=item2id, corpus=corpus)


def replay_matrix(output, *, knn, user2id, item2id, corpus):
    output = Path(output)
    config = json.loads((output / 'config.json').read_text())['config']
    frozen = json.loads((output / 'frozen.json').read_text())
    pool_path = output / 'candidate_sets.jsonl'
    if file_hash(pool_path) != frozen['candidate_sets_sha256'] or file_hash(output / 'config.json') != frozen['config_sha256']:
        raise ValueError('Frozen candidate/config checksum mismatch')
    id2user = {v: k for k, v in user2id.items()}
    quality, paired_values, rank_pairs, times, overlaps, inputs = {}, {}, {}, {}, {}, {}
    failures = {}
    baseline = BaselineScorer(knn)
    with (output / 'ranked.jsonl').open('x', encoding='utf-8') as ranked_stream, pool_path.open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            u, mode, budget, segment = row['user_idx'], row['mode'], row['budget'], row['segment']
            if any(set(pool) & set(row['seen']) for pool in row['pools'].values()):
                raise ValueError('Frozen pool contains seen items')
            if budget == min(config['budgets']):
                inputs.setdefault((mode, segment), []).append(row['no_input'])
            attribution = row['source_evidence']
            peak = max((r['score'] for r in attribution), default=1.)
            evidence = {item2id[r['item_id']]: r['score'] / peak for r in attribution}
            for scope in ('all', segment):
                for name, value in row['latency'].items():
                    times.setdefault((mode, budget, scope, name), []).append(value)
                for name, value in row['overlap'].items():
                    overlaps.setdefault((mode, budget, scope, name), []).append(value['jaccard'])
            for source, pool in row['pools'].items():
                recall = _quality(pool, row['targets'], budget)
                for scope in ('all', segment):
                    key = (mode, source, budget, scope, 'retrieval', budget)
                    quality.setdefault(key, []).append(recall)
                    if recall['recall'] is not None:
                        paired_values.setdefault((mode, source, budget, scope), {})[u] = recall['recall']
                for scorer_mode in config['scoring']['modes']:
                    scorer = baseline if scorer_mode == 'baseline' else EvidenceScorer(baseline, evidence,
                        mode=scorer_mode, popularity_weight=config['scoring']['popularity_weight'],
                        evidence_weight=config['scoring']['evidence_weight'])
                    started = time.perf_counter()
                    ordered = []
                    if pool:
                        response = RankTool(scorer, user2id, item2id, corpus=corpus)(
                            user_id=id2user[u], candidates=pool, top_k=max(config['rank_ks']), exclude_seen=True)
                        if not response.ok:
                            raise RuntimeError(f'RankTool failed: {response}')
                        ordered = [r['item_id'] for r in response.data['ranked']]
                    seconds = time.perf_counter() - started
                    ranked_stream.write(json.dumps({'user_idx': u, 'mode': mode, 'budget': budget,
                        'source': source, 'scorer': scorer_mode, 'ranked': ordered, 'seconds': seconds}) + '\n')
                    for scope in ('all', segment):
                        times.setdefault((mode, budget, scope, f'rank/{source}/{scorer_mode}'), []).append(seconds)
                        for k in config['rank_ks']:
                            key = (mode, source, budget, scope, scorer_mode, k)
                            scores = _quality(ordered, row['targets'], k)
                            quality.setdefault(key, []).append(scores)
                            if scores['recall'] is not None:
                                for metric in ('recall', 'ndcg', 'mrr', 'hit_rate'):
                                    rank_pairs.setdefault((mode, source, budget, scope, scorer_mode, k, metric), {})[u] = scores[metric]
                        if budget == config['gates']['primary_budget']:
                            rank_k = 10 if 10 in config['rank_ks'] else max(config['rank_ks'])
                            top_scores = _quality(ordered, row['targets'], rank_k)
                            fkey = (mode, source, budget, scope, scorer_mode, rank_k)
                            bucket = failures.setdefault(fkey, {
                                'users': 0, 'empty_targets': 0, 'no_input': 0,
                                'all_targets_ineligible': 0, 'retrieval_miss': 0,
                                'ranking_miss': 0, 'top_k_hit': 0})
                            bucket['users'] += 1
                            total_targets = len(row['targets'])
                            ineligible_count = row.get('ineligible_target_count', 0)
                            if total_targets == 0:
                                bucket['empty_targets'] += 1
                            elif ineligible_count >= total_targets:
                                bucket['all_targets_ineligible'] += 1
                            elif top_scores['hit_rate']:
                                bucket['top_k_hit'] += 1
                            elif recall['hit_rate']:
                                bucket['ranking_miss'] += 1
                            else:
                                bucket['retrieval_miss'] += 1
                                if row['no_input']:
                                    bucket['no_input'] += 1
    def label(key):
        return '/'.join(map(str, key))
    errors = {}
    for line in (output / 'candidate_sets.jsonl').open(encoding='utf-8'):
        row = json.loads(line)
        for name in row.get('errors', {}):
            errors[name] = errors.get(name, 0) + 1
    fallback_users = {}
    for line in pool_path.open(encoding='utf-8'):
        row = json.loads(line)
        key = f"{row['mode']}/{row['segment']}"
        fallback_users.setdefault(key, set()).update([row['user_idx']] if row.get('fallback_used', False) else [])
    metrics = {'quality': {label(key): {'users': len(rows), 'eligible_users': sum(r['recall'] is not None for r in rows),
        **{metric: float(np.mean([r[metric] for r in rows if r[metric] is not None]))
           if any(r[metric] is not None for r in rows) else None for metric in ('recall', 'hit_rate', 'ndcg', 'mrr')}}
        for key, rows in quality.items()},
        'latency': {label(key): _latency(values) for key, values in times.items()},
        'mean_source_jaccard': {label(key): float(np.mean(values)) for key, values in overlaps.items()},
        'fallback_users': {key: len(users) for key, users in fallback_users.items()},
        'paired_recall_deltas': {}, 'paired_ranking_deltas': {},
        'query_input': {label(k): {'users': len(v), 'no_input': sum(v), 'query_coverage': 1-sum(v)/len(v)} for k,v in inputs.items()},
        'failure_breakdown': {label(k): v for k, v in failures.items()},
        'errors': {'by_source': errors, 'count': sum(errors.values()),
                   'policy': 'component failures are reported separately; they are not retrieval hits'}, 'gates': {}}
    for key, values in paired_values.items():
        mode, source, budget, scope = key
        references = [(mode, 'bm25', budget, scope), ('latest_title', source, budget, scope)]
        for reference in references:
            if reference != key and reference in paired_values:
                metrics['paired_recall_deltas'][label(key) + '-vs-' + label(reference)] = _paired(
                    values, paired_values[reference], config['seed'], config['bootstrap_samples'])
    for key, values in rank_pairs.items():
        mode, source, budget, scope, scorer_mode, k, metric = key
        references = [(mode, source, budget, scope, 'baseline', k, metric),
                      ('latest_title', source, budget, scope, scorer_mode, k, metric)]
        for reference in references:
            if reference != key and reference in rank_pairs:
                metrics['paired_ranking_deltas'][label(key) + '-vs-' + label(reference)] = _paired(
                    values, rank_pairs[reference], config['seed'], config['bootstrap_samples'])
    gate = config['gates']
    allowed_gates = {
        'recency_weighted/fused-vs-latest_title/fused': ('recency_weighted', 'fused', 'latest_title', 'fused'),
        'recency_weighted/fused-vs-recency_weighted/bm25': ('recency_weighted', 'fused', 'recency_weighted', 'bm25'),
        'recency_weighted/hybrid-vs-recency_weighted/bm25': ('recency_weighted', 'hybrid', 'recency_weighted', 'bm25'),
    }
    if gate['comparison'] not in allowed_gates:
        raise ValueError('Unsupported gate comparison')
    left_mode, left_src, right_mode, right_src = allowed_gates[gate['comparison']]
    budget = gate['primary_budget']
    key = f'{left_mode}/{left_src}/{budget}/all-vs-{right_mode}/{right_src}/{budget}/all'
    segments = sorted({k[3] for k in paired_values if k[3] != 'all'})
    comparisons = [metrics['paired_recall_deltas'].get(
        f'{left_mode}/{left_src}/{budget}/{s}-vs-{right_mode}/{right_src}/{budget}/{s}') for s in segments]
    metrics['gates'] = _gate(gate, metrics['paired_recall_deltas'].get(key), [c for c in comparisons if c],
                                   metrics['latency'].get(f'{left_mode}/{budget}/all/retrieval_total'))
    if 'ann_validation' in config:
        limits = config['ann_validation']
        arm = {}
        for scope in ['all', *segments]:
            def delta(table, tail):
                def values(source):
                    return table.get(('recency_weighted', source, 200, scope, *tail), {})
                return _paired(values('ann_fused'), values('fused'), config['seed'], config['bootstrap_samples'])
            arm[scope] = {'recall200': delta(paired_values, ()),
                          'ndcg10': delta(rank_pairs, ('baseline', 10, 'ndcg'))}
        latency = metrics['latency'].get('recency_weighted/200/all/ann_search', {})
        neighbor_overlap = []
        with pool_path.open(encoding='utf-8') as stream:
            for line in stream:
                row = json.loads(line)
                if row['budget'] == 200 and row['pools'].get('dense'):
                    exact_ids = set(row['pools']['dense'])
                    neighbor_overlap.append(len(exact_ids & set(row['pools'].get('ann_dense', []))) / len(exact_ids))
        checks = [arm['all'][k]['ci95'] for k in ('recall200', 'ndcg10')]
        exact_ndcg = metrics['quality']['recency_weighted/fused/200/all/baseline/10']['ndcg']
        status = 'insufficient_data'
        if all(checks) and latency.get('n', 0) >= limits['min_timed_queries'] and exact_ndcg and not errors:
            passed = (checks[0][0] >= -limits['max_recall_loss'] and checks[1][0] >= -limits['max_ndcg_loss']
                      and latency['p95_seconds'] <= limits['max_search_p95_seconds'])
            status = 'pass' if passed else 'fail'
        metrics['ann_validation'] = {'status':'diagnostic_only' if config.get('diagnostic_only') else status,
                                     'paired_fused_deltas':arm, 'filtered_hnsw_search':latency,
                                     'exact_neighbor_overlap200': {
                                         'queries': len(neighbor_overlap),
                                         'mean': float(np.mean(neighbor_overlap)) if neighbor_overlap else None,
                                         'min': float(np.min(neighbor_overlap)) if neighbor_overlap else None},
                                     'diagnostic_note': 'neighbor overlap is diagnostic; the gate uses paired target deltas'}
    if file_hash(pool_path) != frozen['candidate_sets_sha256']:
        raise ValueError('Candidate pools changed during ranking replay')
    (output / 'metrics.json').write_text(json.dumps(metrics, indent=2), encoding='utf-8')
    hashes = {name: file_hash(output / name) for name in ('config.json', 'candidate_sets.jsonl', 'frozen.json', 'ranked.jsonl', 'metrics.json')}
    (output / 'artifact_hashes.json').write_text(json.dumps({'status': 'complete', 'hashes': hashes}, indent=2))
    return metrics
