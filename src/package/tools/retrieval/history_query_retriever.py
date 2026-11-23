"""Runtime/evaluation adapter for explicit history queries; SearchTool stays unchanged."""

import time
import numpy as np

from .build_history_query import build_history_query
from .fuse_candidates import fuse_candidates
from .tokenize_search_query import tokenize_search_query


class HistoryQueryRetriever:
    def __init__(self, search, vector_store=None, encoder=None, *, eligible_ids=None, block_rows=32768,
                 bm25_index=None):
        if block_rows <= 0 or (vector_store is not None and encoder is None):
            raise ValueError('Invalid dense retriever configuration')
        self.search, self.store, self.encoder = search, vector_store, encoder
        self.block_rows = block_rows
        self.bm25_index = bm25_index
        self.valid = None
        self.bm25_valid = None
        if vector_store is not None:
            if eligible_ids is None:
                raise ValueError('Dense retrieval requires an explicit eligible catalog')
            eligible = set(eligible_ids)
            self.valid = np.fromiter((i in eligible for i in vector_store.item_ids), dtype=bool,
                                     count=len(vector_store.item_ids))
        if bm25_index is not None:
            if eligible_ids is None:
                raise ValueError('SparseBM25Index retrieval requires an explicit eligible catalog')
            self.bm25_valid = bm25_index.eligible_mask(eligible_ids)

    def retrieve(self, history, *, seen, limit, cutoff=None, mode='latest_title', max_items=3,
                 decay=.5, normalization='raw', rrf_k=60, ann_search=None, memory_snapshot=None,
                 exact_dense=True, use_ann_as_dense=False):
        if limit <= 0:
            raise ValueError('Positive retrieval limit required')
        if use_ann_as_dense and ann_search is None:
            raise ValueError('use_ann_as_dense requires ann_search')
        query = build_history_query(history, mode=mode, max_items=max_items, decay=decay,
                                    cutoff=cutoff, normalization=normalization)
        seen = set(seen)
        result = {'query': query, 'bm25': [], 'dense': [], 'hybrid': [], 'latency': {}, 'errors': {}}
        started = time.perf_counter()
        # Query each component separately when needed: exclusion happens before Top-K.
        if query['text'] and tokenize_search_query(query['text']):
            if self.bm25_index is not None:
                result['bm25'] = self.bm25_index.search(
                    query['text'], valid_mask=self.bm25_valid, seen=seen, limit=limit)
            else:
                response = self.search(query=query['text'], filters={'exclude_item_ids': sorted(seen)}, limit=limit)
                self.search.logger.records.clear()
                if not response.ok:
                    raise RuntimeError(f'BM25 tool failure: {response}')
                result['bm25'] = [r['item_id'] for r in response.data['candidates']]
        result['latency']['bm25'] = time.perf_counter() - started
        started = time.perf_counter()
        components = [c for c in query['components'] if c['text']]
        vector = None
        if self.store is not None and components:
            values = np.asarray(self.encoder.encode([c['text'] for c in components]), dtype=np.float32)
            if values.shape != (len(components), self.store.dimension) or not np.isfinite(values).all():
                raise ValueError('Invalid query encoder output')
            component_norms = np.linalg.norm(values, axis=1, keepdims=True)
            if np.any(component_norms <= 0):
                raise ValueError('Query encoder returned zero component vector')
            values = values / component_norms
            vector = np.average(values, axis=0, weights=[c['weight'] for c in components])
            norm = np.linalg.norm(vector)
            if norm <= 0:
                raise ValueError('History aggregation returned zero vector')
            vector /= norm
            result['latency']['dense_encode'] = time.perf_counter() - started
            if ann_search is not None:
                trace = None
                if memory_snapshot:
                    trace = {'before_ann': memory_snapshot()}
                    result['ann_trace'] = trace
                ann_started = time.perf_counter()
                if trace is not None:
                    result['ann_dense'] = ann_search(vector, self.valid, seen, limit, stats=trace)
                else:
                    result['ann_dense'] = ann_search(vector, self.valid, seen, limit)
                result['latency']['ann_search'] = time.perf_counter() - ann_started
                if trace is not None:
                    trace['ann_seconds'] = result['latency']['ann_search']
                    trace['after_ann'] = memory_snapshot()
        result['query_vector'] = vector
        result['no_input'] = not bool(components)
        if use_ann_as_dense:
            result['dense'] = list(result.get('ann_dense', []))
            result['latency']['dense'] = time.perf_counter() - started
            hybrid_started = time.perf_counter()
            if self.store is not None:
                result['hybrid'] = [r['item_id'] for r in fuse_candidates(
                    {'bm25': result['bm25'], 'dense': result['dense']}, budget=limit, rrf_k=rrf_k, excluded=seen)]
            result['latency']['hybrid_fusion'] = time.perf_counter() - hybrid_started
            return result
        result['latency']['dense'] = time.perf_counter() - started - result['latency'].get('ann_search', 0.)
        if exact_dense:
            self.complete_exact(result, seen=seen, limit=limit, rrf_k=rrf_k, memory_snapshot=memory_snapshot)
        return result

    def complete_exact(self, result, *, seen, limit, rrf_k=60, memory_snapshot=None):
        # Adds the exact dense reference and BM25+dense hybrid to a retrieve() result.
        # Evaluation may defer this catalog scan until every timed ANN query has run.
        seen = set(seen)
        vector = result.get('query_vector')
        trace = result.get('ann_trace') if memory_snapshot else None
        started = time.perf_counter()
        if vector is not None:
            if trace is not None:
                trace['before_exact'] = memory_snapshot()
            result['dense'] = self._exact_topk(vector, seen, limit)
            if trace is not None:
                trace['exact_seconds'] = time.perf_counter() - started
                trace['after_exact'] = memory_snapshot()
        # Dense latency remains query encode + exact scan, excluding ANN.
        result['latency']['dense'] = result['latency'].get('dense', 0.) + time.perf_counter() - started
        started = time.perf_counter()
        if self.store is not None:
            result['hybrid'] = [r['item_id'] for r in fuse_candidates(
                {'bm25': result['bm25'], 'dense': result['dense']}, budget=limit, rrf_k=rrf_k, excluded=seen)]
        result['latency']['hybrid_fusion'] = time.perf_counter() - started
        return result

    def _exact_topk(self, vector, seen, limit):
        ids = self.store.item_ids
        best_ids, best_scores = [], np.empty(0, dtype=np.float32)
        for start in range(0, len(ids), self.block_rows):
            stop = min(start + self.block_rows, len(ids))
            mask = self.valid[start:stop].copy()
            mask &= np.fromiter((i not in seen for i in ids[start:stop]), dtype=bool, count=stop-start)
            positions = np.flatnonzero(mask) + start
            if not len(positions):
                continue
            scores = self.store.embeddings[positions] @ vector
            chosen = np.lexsort((ids[positions], -scores))[:limit]
            keys = [str(i) for i in ids[positions[chosen]]]
            merged_ids = best_ids + keys
            merged_scores = np.concatenate((best_scores, scores[chosen]))
            pick = np.lexsort((np.asarray(merged_ids), -merged_scores))[:limit]
            best_ids = [merged_ids[i] for i in pick]
            best_scores = merged_scores[pick]
        return best_ids
