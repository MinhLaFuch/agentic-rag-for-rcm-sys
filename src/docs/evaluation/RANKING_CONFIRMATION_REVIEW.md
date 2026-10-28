# Validation confirmation review — exp_008

## Execution and integrity

The experiment completed in **6,917.39 seconds (1 h 55 min 17 s)**. Its checkpoint
session is `complete`. It used validation, seed 42, 5,000 sampled users per segment,
weights 1e-6/0.01, the fixed historical static-catalog policy, ASCII-fold queries,
neighbors 20, five seed items, three query-history items and budget 100/source.

Read-only checks verified:

* Both published JSONL SHA256 hashes, both mapping assignment hashes and all
  three split content hashes.
* Exactly 15,000 distinct sampled candidate users and **60,000 scored records**
  (two weights, two merges), with no duplicate stream/user records.
* Baseline/tuned candidates and ground truth match per user/merge. Ranked IDs
  are unique members of the candidate input, score order is valid, fetch failures
  are zero, and every published ranking metric at K=5,10,20 was recomputed.
* No ItemCF/SemanticSearch errors and no queries emptied by normalization.
  Cold users have no history query by design.
* Three sparse and two warm users have only repeat targets. They remain in
  operational results and are excluded from novel-target ranking quality as
  specified. Quality denominators are 5,000/4,997/4,998, not 5,000 for every group.

`baseline_confirmation: null` is expected: this was fresh retrieval for a larger
sample, not a frozen replay of exp_006. The within-experiment pairing is verified.
Metadata policy remains a static-catalog proxy, not a fully causal benchmark.

## Primary quality comparison (union_rr)

| Segment | Baseline NDCG@10 | Weight 0.01 | Relative delta | Improved/worse users |
|---|---:|---:|---:|---:|
| Cold | 0.004313177 | 0.004313177 | 0% | 0 / 0 |
| Sparse | 0.001972228 | 0.002048933 | +3.89% | 5 / 2 |
| Warm | 0.001155289 | 0.001206506 | +4.43% | 5 / 0 |

Sparse Recall/Hit Rate@10 are unchanged. Warm Recall@10 rises from 0.166787%
to 0.168121%; Hit Rate@10 rises from 0.440176% to 0.460184%: one additional
warm user has a top-10 hit. Cold quality is unchanged. Top-10 catalog coverage
declines slightly for sparse/warm. No post-merge candidates are lost to seen or
unscored filtering.

The same absolute NDCG deltas occur for union_all, whose warm baseline/tuned
NDCG@10 are 0.001115488/0.001166705. Merges share the same users and are not
independent replications. Sequential latency measurements do not establish a
causal speed improvement from changing the scalar weight.

## Confirmation outside the selection pilot

The larger sample includes all 3,000 pilot users. The primary confirmation view
therefore excludes them: 12,000 new sampled users, 11,995 with novel targets.

| New-user segment | Eligible users | Baseline NDCG@10 | Weight 0.01 | Improved/worse |
|---|---:|---:|---:|---:|
| Cold | 4,000 | 0.004477053 | 0.004477053 | 0 / 0 |
| Sparse | 3,997 | 0.002013504 | 0.002018622 | 2 / 2 |
| Warm | 3,998 | 0.001209523 | 0.001260766 | 4 / 0 |

The pilot's sparse +20% relative gain does not persist at that magnitude among
new users. There is a small positive warm signal, based on only four users.

### Uncertainty

Per-user metric deltas were recomputed from scored.jsonl. Paired percentile
bootstrap: 20,000 empirical resamples, NumPy seed 42, separately within segments.
Multinomial sampling over unique delta values implements the same empirical
paired bootstrap without allocating a large resampling-index matrix.

New-only union_rr NDCG@10 mean deltas and exploratory 95% intervals:

* Sparse: **0.000005118**, interval **[-0.000019533, 0.000034108]**.
* Warm: **0.000051243**, interval **[0.000001731, 0.000114142]**.
* Cold: unchanged in this sample.

Using declared segment population shares, the new-only population-standardized
NDCG estimate rises from 0.001719904 to 0.001749985 (+1.75% relative). The
stratified percentile interval for its delta is [0.000001254, 0.000066215]. These
are estimates from the sample; original population shares approximate shares
among users eligible for novel-target metrics.

Because only eight new users have nonzero NDCG changes (six improve, two worsen),
an exact paired sign-flip randomization sensitivity check was also calculated.
For the new-only population-standardized delta, the **two-sided p-value is
0.078125** (all 256 assignments). The one-sided value is 0.0390625, but no
one-sided decision rule was predeclared; it must not be selected after seeing
the result. The sign-flip check assumes exchangeability of paired method labels
under its null. It is a sensitivity analysis, not a universal replacement for
the bootstrap mean interval.

The full sample's two-sided value is 0.008789, but that view includes users
already used to select the candidate. It does not establish independent
confirmation. Bootstrap and randomization checks give mixed strength of evidence
with very sparse changes; do not interpret the positive percentile interval
alone as robust production qualification. No multiple-comparison adjustment was
applied; the two merges are correlated.

## Decision and next step

* **Experiment valid; do not rerun exp_008 merely because it completed.**
* Keep 1e-6 as the production/control configuration. Retain 0.01 as an offline
  candidate with a modest warm-user signal, not a confirmed general improvement.
* Stop expanding the popularity-weight grid for now. The changes affect very few
  users and absolute recommendation quality remains low. Investigate the next
  retrieval/ranking bottleneck on these saved candidates before spending another
  large run on nearby weights.
* If production promotion of 0.01 is the objective, predeclare the primary metric,
  minimum useful effect and inference rule; confirm on an additional untouched
  validation-user cohort with segment and cost guardrails. Do not use the test
  set for parameter selection or switch to a one-sided rule post hoc.

This review did not modify implementation, production configs or old artifacts,
and did not start training, another evaluation or a test suite.
