# Validation follow-up decision — 2026-11-03

## Evidence

All full runs share 5,096,026 validation users, the same split hashes and the
same manifest identity. The item-familiarity buckets consistently refer to CF
train-core. No test quality metrics have been evaluated.

| Full validation model | Experiment | Recall@10 | NDCG@10 |
|---|---|---:|---:|
| Core popularity | baselines/exp_004 | 0.007754 | 0.003148 |
| Original core CF + fallback | baselines/exp_004 | 0.005222 | 0.002328 |
| Full-train popularity | baselines/exp_006 | 0.009109 | 0.003985 |
| Normalized CF + full-train popularity, weight 4 | baselines/exp_005 | 0.009359 | 0.004096 |

The selected hybrid improves 2.75% Recall@10 and 2.77% NDCG@10 over the stronger
popularity control. This is a descriptive validation result, not a significance
claim or untouched-test confirmation. Its larger gain over exp_004 includes the
effect of adding full-train popularity, not just CF.

The outside-core history-title BM25 pilot (`outside_core_content/exp_003`) has
zero hits at candidate budget 100 on 300 diagnostic users. It also has 65
timeouts among 200 users with history and no query for 100 cold users. RRF60
fusion shows no measured benefit. This variant is not selected for the baseline.
It does not rule out better content representations or genuine user-intent data.

## Baseline candidate to freeze before test

- CF: frozen Stage 4 train-core ItemKNN, 20 neighbors, validated cache and mapping.
- Scoring: per-user max-normalized CF plus 4 times normalized full pre-target
  history popularity; exclude all seen items; deterministic index tie breaks.
- Validation history: train. Prospective test history: train + validation, with
  CF similarity still frozen on train-core, matching the current Stage 4 protocol.
- Metrics: K=5,10,20; primary NDCG@10; retain all target-bearing users and report
  cold/sparse/warm plus core/non-core target metrics without dropping hard cases.
- Controls: core popularity and full pre-target-history popularity. Preserve the
  broader popularity source explicitly in provenance and per-model fit splits.
- Content fusion: off for this candidate. Agent/fixed-candidate ranking policies
  are separate experimental pipelines and have not been switched to this model.

This file documents a reviewable baseline candidate; it does not launch test or
declare the complete agentic system evaluated. Freeze the final request/cohort,
catalog policy, code/environment and model settings before any test quality run.
Historical catalog gating remains a first-seen proxy; mutable price/rating data
cannot be treated as observed historical values.

## Data completion

The preparation of `multi_domain_v2_audit_20261030` is complete: clean, merge,
temporal splits, full/fit-core mappings, corpus/cache and manifest checks.
The requested stronger popularity control and content diagnostic are now also
complete. There is no additional cleaning/splitting step required to force
cold-item metrics above zero. The remaining work is final evaluation protocol
freeze and system/test evaluation, with cold-start limitations disclosed.
