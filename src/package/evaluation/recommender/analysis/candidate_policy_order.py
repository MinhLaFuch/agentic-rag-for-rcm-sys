"""Evaluation-only orderings; no target labels enter these policies."""


def candidate_policy_order(pool, sources, policy):
    if len(pool) != len(set(pool)):
        raise ValueError("duplicate candidate pool")
    allowed = set(pool)
    if policy == "rrf_60":
        scores = dict.fromkeys(pool, 0.)
        for names in sources.values():
            for rank, item in enumerate(dict.fromkeys(names), 1):
                if item in allowed:
                    scores[item] += 1. / (60. + rank)
        return sorted(pool, key=lambda i: -scores[i])
    if policy != "popularity_first":
        raise ValueError("unsupported evaluation policy")
    return list(dict.fromkeys([i for s in ("popularity", "item_cf", "semantic")
                               for i in sources[s] if i in allowed] + pool))
