"""Deterministic quota-capped RRF with complete retained-source attribution."""

import math


def fuse_candidates(sources, *, budget, quotas=None, weights=None, method="rrf", rrf_k=60,
                    excluded=()):
    """Quotas cap unique unseen input rows per source; output never exceeds budget.

    IDs must be strings. Stable ties use item_id ascending, independent of dict
    insertion order. Weights of zero disable a source. No score-scale assumptions.
    """
    if type(budget) is not int or budget <= 0 or method not in ('rrf', 'weighted_rrf'):
        raise ValueError('Invalid fusion budget/method')
    if not math.isfinite(rrf_k) or rrf_k <= 0:
        raise ValueError('rrf_k must be positive')
    quotas, weights = quotas or {}, weights or {}
    if (set(quotas) | set(weights)) - set(sources):
        raise ValueError('Unknown fusion source in quota/weight config')
    excluded, rows = set(excluded), {}
    for source in sorted(sources):
        quota, weight = quotas.get(source, budget), weights.get(source, 1.)
        if type(quota) is not int or quota < 0 or not math.isfinite(weight) or weight < 0:
            raise ValueError('Quotas/weights must be nonnegative and finite')
        if method == 'rrf' and weight != 1:
            raise ValueError('Non-unit weights require weighted_rrf')
        unique, rank = set(), 0
        if not weight or not quota:
            continue
        for item in sources[source]:
            if not isinstance(item, str):
                raise TypeError('Fusion item IDs must be strings')
            if item in excluded or item in unique:
                continue
            if rank >= quota:
                break
            unique.add(item)
            rank += 1
            row = rows.setdefault(item, {'item_id': item, 'score': 0., 'source_ranks': {}})
            row['score'] += weight / (rrf_k + rank)
            row['source_ranks'][source] = rank
    result = sorted(rows.values(), key=lambda row: (-row['score'], row['item_id']))[:budget]
    for row in result:
        row['retrieval_sources'] = sorted(row['source_ranks'])
    return result
