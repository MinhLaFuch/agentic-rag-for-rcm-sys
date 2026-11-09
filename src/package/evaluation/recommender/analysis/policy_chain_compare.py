"""Controlled policy/fetch measurements shared by frozen and fresh evaluation."""
import random
import time

from .candidate_policy_order import candidate_policy_order


def policy_chain_compare(record, merge, baseline, fetch, *, seed, warmup=False, eligible=None):
    """Callbacks receive no labels. Retrieval has already run once, if requested.

    baseline(pool) returns {'ids': [...], 'scores': [...]}; fetch returns metadata rows.
    No retries/fallback: failures remain visible in emitted records.
    """
    pool = record["candidate_sets"][merge]
    if len(pool) != len(set(pool)):
        raise ValueError("invalid duplicate candidate input")
    policies = ["baseline", "popularity_first", "rrf_60"]
    random.Random(f"{seed}:{record['user_idx']}:{merge}").shuffle(policies)
    results = []
    for position, policy in enumerate(policies):
        start = time.perf_counter()
        ranked, scores, error, metadata_error = [], None, None, None
        filtered = pool
        try:
            filtered = eligible(pool) if eligible else pool
            if len(filtered)!=len(set(filtered)) or not set(filtered)<=set(pool):
                raise ValueError("invalid eligibility filter")
            if policy == "baseline" or record["segment"] == "cold":
                output = baseline(filtered)
                ranked, scores = output["ids"], output["scores"]
                if len(scores) != len(ranked):
                    raise ValueError("baseline score length mismatch")
            else:
                ranked = candidate_policy_order(filtered, record["sources_after_seen_filter"], policy)
            if len(ranked) != len(set(ranked)) or set(ranked) != set(filtered):
                raise ValueError("policy changed candidate pool")
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            ranked, scores = [], None
        policy_seconds = time.perf_counter() - start
        before_fetch = time.perf_counter()
        metadata = []
        if error is None:
            try:
                metadata = fetch(ranked[:20])
                ids = [r["item_id"] for r in metadata]
                if len(ids) != len(set(ids)) or set(ids) != set(ranked[:20]):
                    raise ValueError("missing, duplicate or unexpected metadata")
            except Exception as exc:
                metadata_error = f"{type(exc).__name__}: {exc}"
        elapsed = time.perf_counter() - start
        results.append(dict(user_idx=record["user_idx"], segment=record["segment"], merge=merge,
                            policy=policy, order_position=position, warmup=warmup,
                            input_candidates=len(pool),eligible_candidates=len(filtered),
                            eligibility_removed=len(pool)-len(filtered),
                            ranked_ids=ranked, scores=scores,
                            delivered_ids=ranked[:20] if error is None and metadata_error is None else [],
                            policy_seconds=policy_seconds,
                            fetch_seconds=time.perf_counter()-before_fetch,
                            policy_fetch_seconds=elapsed, policy_error=error,
                            metadata_error=metadata_error, fallback=False,
                            retrieval_errors=record["source_failures"],
                            targets_unseen_in_fit=record["targets_unseen_in_fit"]))
    return results
