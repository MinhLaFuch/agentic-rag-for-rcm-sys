from __future__ import annotations

from collections import Counter

from ..recommenders.fit_provenance import fit_provenance


def evaluation_protocol(*, eval_on, tag, fit_df, target_df, user2id, item2id,
                        segments, sampled, metadata_policy, evaluation_kind="ranking"):
    if fit_df.empty or target_df.empty or "timestamp" not in fit_df or "timestamp" not in target_df:
        raise ValueError("non-empty fit/target with timestamps required")
    for frame in (fit_df, target_df):
        if frame.timestamp.isna().any() or (frame.timestamp <= 0).any():
            raise ValueError("timestamps must be present and positive")
    if int(fit_df.timestamp.max()) >= int(target_df.timestamp.min()):
        raise ValueError("temporal protocol violation: fit must strictly precede target")
    if metadata_policy["as_of_timestamp"] != int(target_df.timestamp.min()):
        raise ValueError("metadata policy cutoff must match target start")
    return {
        "version": 2, "evaluation_kind": evaluation_kind,
        "item_knn": fit_provenance(fit_df, user2id=user2id, item2id=item2id, eval_on=eval_on, tag=tag),
        "fit_timestamp_max": int(fit_df.timestamp.max()),
        "target_timestamp_min": int(target_df.timestamp.min()),
        "metadata_policy": metadata_policy,
        "label_policy": "all observed review user-item pairs are binary positives, independent of stars",
        "cohort_policy": "existing pre-split filtered cohort; future-informed selection",
        "history_size": "unique fit items, consistent with binary CSR",
        "segment_population_users": dict(Counter(segments.values())),
        "segment_sample_users": {s: len(us) for s, us in sampled.items()},
        "sampling": "seeded per-segment cap; pooled sample average is not population-weighted",
        "item_warm_definition": "any user interacted in fit; distinct from same-user repeat",
        "candidate_target_denominator": "all unique target items per user; seen filtering may make repeat targets unretrievable",
        "ranking_target_denominator": ("request.targets; ambiguous requests have no quality ground truth" if evaluation_kind == "agent"
                                       else "novel target items per user; empty-ground-truth users excluded"),
        "query_provenance": "fit-history title proxy, not observed user query; target-metadata queries must be oracle",
    }
