# Ranking tuning review: exp_007

Reviewed against local artifacts after completion. No production configuration,
source dataset, existing experiment or checkpoint was modified by this review.

## Integrity and execution

* Validation, seed 42, 1,000 users each in cold/sparse/warm; five scorer weights,
  two merges; **30,000 scored records**, exactly 3,000 users per merge/variant.
* Artifact SHA256 checks pass for candidate_lists.jsonl and scored.jsonl.
* All variants receive identical candidate sets and ground truth per user/merge.
  The 3,000 candidate objects equal exp_006. File byte hashes differ because
  JSONL was exported with LF instead of legacy CRLF, not because inputs changed.
* Baseline confirmation against exp_006 passes on both merges: every user's
  ranked IDs and scores, aggregate quality and coverage. Maximum recorded
  aggregate metric error: **1.7347e-18**.
* Reported active runtime including initial hashing: **492.32 s (8 min 12 s)**.
  This is fixed-candidate scoring with source retrieval timings copied; it is
  not a fresh retrieval/end-to-end performance measurement.
* The checkpoint has session status `complete` and points to exp_007. The
  published timing snapshot says `running` because it was captured before
  closing the session; this does not mean the run is still active.
* Source candidate health: no ItemCF/SemanticSearch errors or emptied queries.
  Retrieval was not executed again in this session.

## Weight decisions

| Weight | NDCG@10 observation | Decision |
|---|---|---|
| 1e-6 | Confirmed baseline | Retain as control |
| 0 | Tiny gain in 2 cold users; all cold candidate scores tie | Do not select from this pilot |
| 1e-4 | Same quality metrics as baseline at K=5,10,20 | No evidence of improvement |
| 1e-3 | Same quality metrics as baseline at K=5,10,20 | No evidence of improvement |
| 1e-2 | Gains in 3 sparse users and 1 warm user | Candidate for larger-sample confirmation only |

For weight 0.01, top-10 metrics are the same between union_rr and union_all:

| Segment | Baseline NDCG@10 | Weight 0.01 | Relative change | Users improved/worse |
|---|---:|---:|---:|---:|
| Cold | 0.003657675 | 0.003657675 | 0% | 0 / 0 |
| Sparse | 0.001807248 | 0.002170088 | +20.08% | 3 / 0 |
| Warm | 0.000938464 | 0.000989576 | +5.45% | 1 / 0 |

Every user's Recall@10 and Hit Rate@10 is unchanged for every tested weight.
The observed gains come from moving existing relevant items higher, not finding
additional top-10 relevant items. Quality remains low in absolute terms.
Coverage changes are small. No post-merge candidates were lost to seen or
unscored filtering for any variant. For weight 0, cold tie pair/boundary rates
are 100%; results depend on existing candidate order. Boundary tie summaries
refer to max-K=20, not K=10.

## Paired uncertainty analysis

Recomputed per-user metrics from scored.jsonl using existing ranking metric
implementations. For each segment, compared each variant against the baseline
on the exact same users. Percentile paired bootstrap: 5,000 resamples of 1,000
users with replacement, NumPy RNG seed 42, segment-stratified; intervals are
exploratory and unadjusted for multiple comparisons.

Weight 0.01 minus baseline, NDCG@10:

| Segment | Mean absolute delta | 95% bootstrap interval |
|---|---:|---:|
| Cold | 0 | [0, 0] |
| Sparse | 0.000362839 | [0, 0.000951973] |
| Warm | 0.000051112 | [0, 0.000153337] |

These intervals include zero. With only four improving users and several
candidate weights examined, the pilot does not establish a reliable population
quality gain. Zero-width intervals for unchanged sample outcomes do not prove
population equivalence. The two merges reuse the same users and are not
independent replication experiments.

Latency measurements vary substantially by run order/segment. No randomized,
repeated timing comparison was performed, so the measured differences do not
establish that one scalar weight is computationally faster.

## Next experiment

Keep production unchanged. Confirm only **1e-6 versus 0.01** on a larger fixed
validation sample, initially 5,000 users per segment if resources permit. Generate
candidate lists once within that new experiment and feed both scorers the same
lists. Do not use `--candidates-from exp_006` for a larger sample: that file only
contains the existing 3,000-user pilot. Keep normalization, budgets, neighbors,
seed items, K and seed fixed. Persist checkpoint/progress and compare paired
results plus coverage and cost before promoting any candidate.

No larger evaluation, test-set tuning or new training was launched during this
review. Full validation, population confirmation and production promotion remain
pending evidence from subsequent experiments.
