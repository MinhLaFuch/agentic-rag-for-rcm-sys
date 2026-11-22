import json
from types import SimpleNamespace

import numpy as np
import pytest
from scipy import sparse
import yaml

from package.tools.retrieval.build_history_query import build_history_query
from package.tools.retrieval.fuse_candidates import fuse_candidates
from package.tools.retrieval.history_query_retriever import HistoryQueryRetriever
from package.tools.retrieval.eligible_catalog_ids import eligible_catalog_ids
from package.tools.retrieval.catalog_title_lookup import catalog_title_lookup
from package.tools.scoring.evidence_scorer import EvidenceScorer
from package.tools.scoring.baseline_scorer import BaselineScorer
from package.embeddings import VectorStore, TextEncoder
from package.tools import SearchTool
from scripts.evaluation.retrieval_matrix import run_matrix, _gate, _paired, _quality
from tests.tools_helpers import VG_A, VG_B, VG_C, EL_A, EL_D


def test_query_modes_no_target_leakage_and_recency_weights():
    history = [{'item_id': 'b', 'title': 'old', 'timestamp': 1},
               {'item_id': 'a', 'title': 'new', 'timestamp': 2},
               {'item_id': 'future', 'title': 'HELD OUT', 'timestamp': 10}]
    baseline = build_history_query(history, cutoff=10)
    assert baseline['text'] == 'new'
    result = build_history_query(list(reversed(history)), cutoff=10, mode='recency_weighted', decay=.5)
    assert result['text'] == 'new old'
    assert [c['weight'] for c in result['components']] == [1., .5]
    assert 'HELD OUT' not in json.dumps(result)
    assert result == build_history_query(history, cutoff=10, mode='recency_weighted', decay=.5)
    assert build_history_query([], cutoff=10)['text'] == ''
    assert build_history_query([{'item_id': 'late', 'title': 'late', 'timestamp': 99}], cutoff=None)['text'] == 'late'
    history[2]['title'] = 'changed target'
    assert result == build_history_query(history, cutoff=10, mode='recency_weighted', decay=.5)


def test_fusion_quota_budget_dedup_attribution_and_permutation():
    sources = {'cf': ['seen', 'b', 'b', 'a'], 'dense': ['a', 'b', 'c']}
    options = dict(budget=2, quotas={'cf': 1, 'dense': 2}, excluded={'seen'})
    result = fuse_candidates(sources, **options)
    assert [r['item_id'] for r in result] == ['b', 'a']
    assert result[0]['source_ranks'] == {'cf': 1, 'dense': 2}
    assert result == fuse_candidates(dict(reversed(list(sources.items()))), **options)
    assert len({r['item_id'] for r in result}) == len(result) <= 2
    assert fuse_candidates({'x': ['b'], 'y': ['a']}, budget=1)[0]['item_id'] == 'a'
    assert fuse_candidates({'x': ['a']}, budget=2, method='weighted_rrf', weights={'x': 0}) == []
    with pytest.raises(ValueError):
        fuse_candidates(sources, budget=2, weights={'missing': 1})


def _model():
    return SimpleNamespace(scores=np.array([1., 100., 0.]), num_items=3,
        user_items=sparse.csr_matrix([[1., 0., 0.]]),
        similarity=sparse.csr_matrix([[0., 0., .01], [0., 0., 0.], [0., 0., 0.]]))


def test_evidence_scorer_preserves_strict_cf_and_cold_fallback():
    scorer = EvidenceScorer(_model(), {1: 1.}, popularity_weight=1., evidence_weight=1.)
    assert scorer.score(0, np.array([2, 1]))[0] > scorer.score(0, np.array([2, 1]))[1]
    cold = scorer.score(-1, np.array([1, 2]))
    assert cold[0] > cold[1]
    assert not scorer.is_known_user(-1)
    ablation = EvidenceScorer(_model(), {1: 1.}, mode='additive_ablation', evidence_weight=1.)
    assert ablation.score(0, np.array([1, 2]))[0] > ablation.score(0, np.array([1, 2]))[1]
    assert BaselineScorer(_model()).name == 'SimpleNamespace'


def test_dense_filters_eligible_and_seen_before_topk(corpus):
    store = VectorStore([VG_A, VG_B, VG_C], np.array([[1., 0.], [.9, .1], [.8, .2]]))
    encoder = TextEncoder(lambda texts: np.tile([[1., 0.]], (len(texts), 1)))
    retriever = HistoryQueryRetriever(SearchTool(corpus), store, encoder, eligible_ids={VG_B, VG_C}, block_rows=1)
    result = retriever.retrieve([{'item_id': VG_A, 'title': 'game', 'timestamp': 1}],
                                cutoff=2, seen={VG_B}, limit=1)
    assert result['dense'] == [VG_C]
    assert VG_B not in result['hybrid']


def test_weighted_vectors_use_multiple_history_items(corpus):
    store = VectorStore([VG_A, VG_B], np.eye(2, dtype=np.float32))
    encoder = TextEncoder(lambda texts: np.array([[1.,0.] if t == 'one' else [0.,1.] for t in texts]))
    retriever = HistoryQueryRetriever(SearchTool(corpus), store, encoder, eligible_ids={VG_A,VG_B})
    history = [{'item_id':'x', 'title':'one','timestamp':2}, {'item_id':'y','title':'two','timestamp':1}]
    latest = retriever.retrieve(history, cutoff=3, seen=set(), limit=2)
    weighted = retriever.retrieve(history, cutoff=3, seen=set(), limit=2, mode='recency_weighted')
    assert len(latest['query']['components']) == 1
    assert len(weighted['query']['components']) == 2
    assert weighted['dense'][0] == VG_A


def test_gates_and_pairing_are_explicit():
    assert _gate(dict(min_recall_delta_ci_low=None, max_p95_seconds=None, max_segment_recall_regression=None), None, [], None)['status'] == 'not_set'
    assert _paired({1:1.,2:0.}, {1:0.,2:0.}, 42, 30)['mean_delta'] == .5
    with pytest.raises(ValueError, match='cohort mismatch'):
        _paired({1:1.}, {2:1.}, 42, 10)
    assert _quality(['a','b'], ['b'], 1)['recall'] == 0
    assert _quality(['a','b'], ['b'], 2)['recall'] == 1


@pytest.mark.parametrize('ann,trace', [(False,False),(True,False),(True,True)])
def test_full_matrix_freezes_pools_and_ranks_same_sets(corpus, tmp_path, monkeypatch, ann, trace):
    ids = sorted([VG_A, VG_B, VG_C, EL_A, EL_D])
    store = VectorStore(ids, np.tile([[1., 0.]], (5,1)))
    encoder = TextEncoder(lambda texts: np.tile([[1., 0.]], (len(texts),1)))
    model = SimpleNamespace(scores=np.array([5.,4.,3.,2.,1.]), num_items=5,
        user_items=sparse.csr_matrix([[1.,0.,0.,0.,0.]]), similarity=sparse.csr_matrix((5,5)))
    class CF:
        logger = SimpleNamespace(records=[])
        def __call__(self, **kwargs):
            return SimpleNamespace(ok=True, data={'candidates':[{'item_id':VG_B}]})
    config = yaml.safe_load(open('src/configs/eval/retrieval_matrix.yaml', encoding='utf-8'))
    config.update(budgets=[2], rank_ks=[1,2], bootstrap_samples=10)
    config['gates']['primary_budget'] = 2
    if ann:
        from scripts.evaluation import ann_validation
        config = yaml.safe_load(open('src/configs/eval/ann_validation.yaml', encoding='utf-8'))
        def search(*args, stats=None):
            if stats is not None:
                stats.update(faiss_seconds=0.,filter_seconds=0.,fetch_total=1,retries=0)
            return [VG_B]
        monkeypatch.setattr(ann_validation, 'build_ann_search', lambda *_: search)
        if trace:
            import sys
            monkeypatch.setitem(sys.modules,'faiss',SimpleNamespace(omp_get_max_threads=lambda:1))
            monkeypatch.setitem(sys.modules,'psutil',SimpleNamespace(
                Process=lambda: SimpleNamespace(memory_info=lambda: SimpleNamespace(rss=100,num_page_faults=5)),
                virtual_memory=lambda: SimpleNamespace(available=200)))
    config_path = tmp_path/'matrix.yaml'
    config_path.write_text(yaml.safe_dump(config))
    output = tmp_path/'output'
    title_requests = []
    def titles(keys):
        title_requests.append(list(keys))
        assert keys == [VG_A]
        return {VG_A: ('game', 'category')}
    metrics = run_matrix(output=output, config_path=config_path, sampled={'sparse':[0]},
        recent={0:[ids.index(VG_A)]}, fit_events={0:[{'item_id':VG_A,'timestamp':1}]*50 + [{'item_id':VG_B,'timestamp':10}]},
        item_text=titles, id2item=dict(enumerate(ids)),
        user2id={'user':0}, item2id={item:i for i,item in enumerate(ids)}, targets={0:{ids.index(VG_B)}}, cutoff=2,
        knn=model, item_cf=CF(), search=SearchTool(corpus), vector_store=store, encoder=encoder,
        corpus=corpus, trace_ann=trace, provenance={'synthetic':True,'protocol':{'item_knn':{'eval_on':'validation'}}})
    assert metrics['gates']['status'] == 'not_set'
    assert title_requests == [[VG_A]]
    if not ann:
        assert metrics['paired_ranking_deltas']
    assert metrics['paired_recall_deltas']
    assert metrics['fallback_users']['recency_weighted/sparse'] == 0
    rows = [json.loads(line) for line in (output/'candidate_sets.jsonl').read_text().splitlines()]
    assert len(rows) == (1 if ann else 3)
    if ann:
        assert rows[0]['pools']['ann_dense']==[VG_B]
        result=metrics['ann_validation']
        assert result['status']==('diagnostic_only' if trace else 'insufficient_data')
        if trace:
            report=json.loads((output/'ann_trace.json').read_text())
            assert report['summary']['timed_queries']==1
            row=report['rows'][0]
            assert row['sequence']==1 and row['before_exact']['rss_bytes']>0
            assert row['fetch_total']==1 and 'page_faults' in row['after_exact'] and 'after_ann' in row
            assert report['summary']['phase_order']=='all timed ANN queries before exact reference'
        assert result['paired_fused_deltas']['all']['ndcg10']['users']==1
        assert 'ann_retrieval_total' in rows[0]['latency'] and 'dense_encode' in rows[0]['latency']
    assert all(not set(pool)&{VG_A} for row in rows for pool in row['pools'].values())
    ranked = [json.loads(line) for line in (output/'ranked.jsonl').read_text().splitlines()]
    for row in ranked:
        pool = next(r['pools'][row['source']] for r in rows if r['mode'] == row['mode'])
        assert set(row['ranked']) <= set(pool)
    assert json.loads((output/'artifact_hashes.json').read_text())['status'] == 'complete'


def test_ann_matrix_times_all_ann_queries_before_exact_reference(corpus, tmp_path, monkeypatch):
    from scripts.evaluation import ann_validation
    ids = sorted([VG_A, VG_B, VG_C, EL_A, EL_D])
    store = VectorStore(ids, np.tile([[1., 0.]], (5,1)))
    encoder = TextEncoder(lambda texts: np.tile([[1., 0.]], (len(texts),1)))
    model = SimpleNamespace(scores=np.array([5.,4.,3.,2.,1.]), num_items=5,
        user_items=sparse.csr_matrix([[1.,0.,0.,0.,0.],[1.,0.,0.,0.,0.]]), similarity=sparse.csr_matrix((5,5)))
    class CF:
        logger = SimpleNamespace(records=[])
        def __call__(self, **kwargs):
            return SimpleNamespace(ok=True, data={'candidates':[{'item_id':VG_B}]})
    events = []
    def search(*args, stats=None):
        events.append('ann')
        return [VG_B]
    monkeypatch.setattr(ann_validation, 'build_ann_search', lambda *_: search)
    exact = HistoryQueryRetriever._exact_topk
    def logged_exact(self, *args):
        events.append('exact')
        return exact(self, *args)
    monkeypatch.setattr(HistoryQueryRetriever, '_exact_topk', logged_exact)
    config_path = tmp_path/'matrix.yaml'
    config_path.write_text(open('src/configs/eval/ann_validation.yaml', encoding='utf-8').read())
    history = [{'item_id':VG_A,'timestamp':1}]
    output = tmp_path/'output'
    run_matrix(output=output, config_path=config_path, sampled={'sparse':[0,1]},
        recent={0:[ids.index(VG_A)],1:[ids.index(VG_A)]}, fit_events={0:history,1:history},
        item_text=lambda keys: {VG_A: ('game', 'category')}, id2item=dict(enumerate(ids)),
        user2id={'user':0,'other':1}, item2id={item:i for i,item in enumerate(ids)},
        targets={0:{ids.index(VG_B)},1:{ids.index(VG_C)}}, cutoff=2, knn=model, item_cf=CF(),
        search=SearchTool(corpus), vector_store=store, encoder=encoder, corpus=corpus,
        provenance={'synthetic':True,'protocol':{'item_knn':{'eval_on':'validation'}}})
    assert events == ['ann', 'ann', 'exact', 'exact']
    rows = [json.loads(line) for line in (output/'candidate_sets.jsonl').read_text().splitlines()]
    assert [r['user_idx'] for r in rows] == [0, 1]
    assert all(r['pools']['dense'] and r['pools']['ann_dense'] == [VG_B] for r in rows)
    assert 'two-pass' in json.loads((output/'config.json').read_text())['ann_timing']
    overlap = json.loads((output/'metrics.json').read_text())['ann_validation']['exact_neighbor_overlap200']
    assert overlap['queries'] == 2 and 0 < overlap['mean'] <= 1


@pytest.mark.parametrize('kind', ['hnsw_flat', 'hnsw_sq8', 'hnsw_fp16'])
def test_ann_index_build_warmup_and_filtering(kind):
    pytest.importorskip('faiss')
    from scripts.evaluation.ann_validation import build_ann_search
    rng = np.random.default_rng(0)
    vectors = rng.standard_normal((300, 8)).astype(np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    ids = np.array([f'item_{i:03d}' for i in range(300)])
    store = SimpleNamespace(dimension=8, embeddings=vectors, item_ids=ids)
    search = build_ann_search(store, {'index': kind, 'm': 8, 'ef_search': 300, 'train_size': 300,
                                      'warmup_queries': 5, 'warmup_limit': 10})
    assert search.build_info['index'] == kind and search.build_info['warmup_queries'] == 5
    valid = np.ones(300, dtype=bool)
    valid[1] = False
    result = search(vectors[1], valid, {'item_002'}, 10)
    assert len(result) == 10 and 'item_001' not in result and 'item_002' not in result


def test_ann_index_rejects_unknown_type_and_bad_warmup():
    pytest.importorskip('faiss')
    from scripts.evaluation.ann_validation import build_ann_search
    store = SimpleNamespace(dimension=2, embeddings=np.eye(2, dtype=np.float32), item_ids=np.array(['a', 'b']))
    with pytest.raises(ValueError, match='Unsupported ANN index'):
        build_ann_search(store, {'index': 'ivf', 'm': 4, 'ef_search': 4})
    with pytest.raises(ValueError, match='warmup_queries'):
        build_ann_search(store, {'m': 4, 'ef_search': 4, 'warmup_queries': -1})


def test_dense_ann_single_pass_skips_exact_and_evaluates_gate(corpus, tmp_path, monkeypatch):
    from scripts.evaluation import ann_validation
    ids = sorted([VG_A, VG_B, VG_C, EL_A, EL_D])
    store = VectorStore(ids, np.tile([[1., 0.]], (5, 1)))
    encoder = TextEncoder(lambda texts: np.tile([[1., 0.]], (len(texts), 1)))
    model = SimpleNamespace(scores=np.array([5., 4., 3., 2., 1.]), num_items=5,
        user_items=sparse.csr_matrix([[1., 0., 0., 0., 0.]]), similarity=sparse.csr_matrix((5, 5)))
    class CF:
        logger = SimpleNamespace(records=[])
        def __call__(self, **kwargs):
            return SimpleNamespace(ok=True, data={'candidates': [{'item_id': VG_B}]})
    ann_calls = []
    def search(*args, stats=None):
        ann_calls.append(1)
        return [VG_B]
    monkeypatch.setattr(ann_validation, 'build_ann_search', lambda *_: search)
    def fail_exact(*args, **kwargs):
        raise AssertionError('dense_ann single-pass must not run exact catalog scan')
    monkeypatch.setattr(HistoryQueryRetriever, '_exact_topk', fail_exact)
    config = yaml.safe_load(open('src/configs/eval/retrieval_matrix_validation_sq8.yaml', encoding='utf-8'))
    config.update(budgets=[2], rank_ks=[1, 2], bootstrap_samples=10)
    config['gates'].update(primary_budget=2, min_recall_delta_ci_low=-1.0, max_p95_seconds=60.0,
                           max_segment_recall_regression=1.0)
    config_path = tmp_path / 'dense_ann.yaml'
    config_path.write_text(yaml.safe_dump(config))
    output = tmp_path / 'out'
    metrics = run_matrix(output=output, config_path=config_path, sampled={'sparse': [0]},
        recent={0: [ids.index(VG_A)]}, fit_events={0: [{'item_id': VG_A, 'timestamp': 1}]},
        item_text=lambda keys: {VG_A: ('game', 'category')}, id2item=dict(enumerate(ids)),
        user2id={'user': 0}, item2id={item: i for i, item in enumerate(ids)}, targets={0: {ids.index(VG_B)}},
        cutoff=2, knn=model, item_cf=CF(), search=SearchTool(corpus), vector_store=store, encoder=encoder,
        corpus=corpus, provenance={'synthetic': True, 'protocol': {'item_knn': {'eval_on': 'validation'}}})
    assert len(ann_calls) == 3
    assert 'ann_validation' not in metrics
    assert metrics['gates']['status'] == 'pass'
    fb = metrics['failure_breakdown']['recency_weighted/fused/2/all/baseline/2']
    assert fb['users'] == 1 and fb['top_k_hit'] + fb['ranking_miss'] + fb['retrieval_miss'] == 1
    cfg_saved = json.loads((output / 'config.json').read_text())
    assert 'single-pass dense_ann' in cfg_saved['ann_timing']


def test_held_out_test_matrix_requires_frozen_flag(corpus, tmp_path):
    ids = sorted([VG_A, VG_B, VG_C, EL_A, EL_D])
    store = VectorStore(ids, np.tile([[1., 0.]], (5, 1)))
    encoder = TextEncoder(lambda texts: np.tile([[1., 0.]], (len(texts), 1)))
    model = SimpleNamespace(scores=np.array([5., 4., 3., 2., 1.]), num_items=5,
        user_items=sparse.csr_matrix([[1., 0., 0., 0., 0.]]), similarity=sparse.csr_matrix((5, 5)))
    class CF:
        logger = SimpleNamespace(records=[])
        def __call__(self, **kwargs):
            return SimpleNamespace(ok=True, data={'candidates': [{'item_id': VG_B}]})
    config = yaml.safe_load(open('src/configs/eval/retrieval_matrix.yaml', encoding='utf-8'))
    config.update(budgets=[2], rank_ks=[1, 2], bootstrap_samples=10)
    config['gates']['primary_budget'] = 2
    config_path = tmp_path / 'val_cfg.yaml'
    config_path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError, match='final_test_frozen'):
        run_matrix(output=tmp_path / 'out', config_path=config_path, sampled={'sparse': [0]},
            recent={0: [ids.index(VG_A)]}, fit_events={0: [{'item_id': VG_A, 'timestamp': 1}]},
            item_text=lambda keys: {VG_A: ('game', 'category')}, id2item=dict(enumerate(ids)),
            user2id={'user': 0}, item2id={item: i for i, item in enumerate(ids)}, targets={0: {ids.index(VG_B)}},
            cutoff=2, knn=model, item_cf=CF(), search=SearchTool(corpus), vector_store=store, encoder=encoder,
            corpus=corpus, provenance={'synthetic': True, 'protocol': {'item_knn': {'eval_on': 'test'}}})


def test_deferred_exact_matches_inline_retrieval(corpus):
    store = VectorStore([VG_A, VG_B, VG_C], np.array([[1., 0.], [.9, .1], [.8, .2]]))
    encoder = TextEncoder(lambda texts: np.tile([[1., 0.]], (len(texts), 1)))
    retriever = HistoryQueryRetriever(SearchTool(corpus), store, encoder, eligible_ids={VG_B, VG_C}, block_rows=1)
    history = [{'item_id': VG_A, 'title': 'game', 'timestamp': 1}]
    inline = retriever.retrieve(history, cutoff=2, seen={VG_A}, limit=2)
    deferred = retriever.retrieve(history, cutoff=2, seen={VG_A}, limit=2, exact_dense=False)
    assert deferred['dense'] == [] and deferred['hybrid'] == []
    retriever.complete_exact(deferred, seen={VG_A}, limit=2)
    assert (deferred['dense'], deferred['hybrid']) == (inline['dense'], inline['hybrid'])


def test_eligibility_uses_bounded_ranges_and_keeps_policy(corpus):
    from package.corpus.apply_metadata_policy import apply_metadata_policy
    apply_metadata_policy(corpus, 'historical_static_catalog', as_of_timestamp=2)
    ids = sorted([VG_A, VG_B, VG_C, EL_A, EL_D, 'ZZ::future'])
    calls = []
    class BoundedCorpus:
        def select(self, sql, params, max_rows):
            assert max_rows <= 2
            assert 'WHERE item_id >= ? AND item_id <= ?' in sql
            calls.append((params, max_rows))
            return corpus.select(sql, params, max_rows=max_rows)
    result = eligible_catalog_ids(BoundedCorpus(), ids, page_size=2)
    assert result == {VG_A, VG_B, VG_C, EL_A, EL_D}
    assert len(calls) == 3


def test_eligibility_rejects_truncation_and_unsorted_ids():
    class Truncated:
        def select(self, *args, **kwargs):
            return [], True
    with pytest.raises(ValueError, match='differs'):
        eligible_catalog_ids(Truncated(), ['a', 'b'])
    with pytest.raises(ValueError, match='sorted'):
        eligible_catalog_ids(Truncated(), ['b', 'a'])


def test_eligibility_does_not_expose_future_catalog_items():
    import pandas as pd
    from package.corpus import ItemCorpus
    from package.corpus.apply_metadata_policy import apply_metadata_policy
    corpus = ItemCorpus.from_dataframe(pd.DataFrame({
        'parent_asin': ['old', 'future'], 'domain': ['D', 'D'],
        'title': ['old item', 'future item'], 'first_seen_ts': [1, 10]}))
    apply_metadata_policy(corpus, 'historical_static_catalog', as_of_timestamp=2)
    assert eligible_catalog_ids(corpus, ['D::future', 'D::old'], page_size=1) == {'D::old'}
    lookup = catalog_title_lookup(corpus)
    assert lookup(['D::future', 'D::old']) == {'D::old': ('old item', '')}


def test_title_lookup_is_bounded_cached_and_has_no_category_join(corpus):
    calls = []
    class TitlesOnly:
        def select(self, sql, params, max_rows):
            assert 'JOIN' not in sql and 'GROUP BY' not in sql
            assert 'main.' not in sql
            assert max_rows <= 2
            calls.append(list(params))
            return corpus.select(sql, params, max_rows=max_rows)
    lookup = catalog_title_lookup(TitlesOnly(), batch_size=2)
    result = lookup([VG_A, VG_B, VG_C, 'missing'])
    assert set(result) == {VG_A, VG_B, VG_C}
    assert len(calls) == 2
    assert lookup([VG_A, 'missing']) == {VG_A: result[VG_A]}
    assert len(calls) == 2
