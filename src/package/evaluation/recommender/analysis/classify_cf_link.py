"""Distinguish absent train signal from top-neighbor truncation."""
import math


def classify_cf_link(seed_support, target_support, cooccurrence, in_cache, cutoff):
    if min(seed_support,target_support,cooccurrence)<0 or cooccurrence>min(seed_support,target_support):
        raise ValueError('invalid unique-pair supports')
    if not cooccurrence:
        return {'reason':'no_train_cooccurrence','cosine':0.}
    cosine=cooccurrence/math.sqrt(seed_support*target_support)
    if in_cache: reason='in_cache'
    elif math.isclose(cosine,cutoff,rel_tol=1e-5,abs_tol=1e-8): reason='truncated_at_tied_cutoff'
    elif cosine<cutoff: reason='truncated_below_cutoff'
    else: reason='above_cutoff_missing_requires_investigation'
    return dict(reason=reason,cosine=cosine)
