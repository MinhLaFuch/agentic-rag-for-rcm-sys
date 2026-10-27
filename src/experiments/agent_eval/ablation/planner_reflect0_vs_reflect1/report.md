# Ablation Comparison: planner_reflect0_vs_reflect1

**Agent A:** planner (group: reflect_0)
**Agent B:** planner (group: reflect_1)
**Bootstrap resamples:** 10000
**Confidence level:** 95.0%
**k:** 10

**Number of paired requests:** 66

**Variance:** Only 1 run per group, cannot compute variance

## Results by Kind (aggregated across segments)

### Kind: ambiguous

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| recall@10 | — | — | — | — | 0 |
| ndcg@10 | — | — | — | — | 0 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| llm_latency_seconds | 3.2475 | 3.8465 | +0.5990 | [-0.2083, 1.8413] | 6 |
| completion_tokens | 95.6667 | 92.0000 | -3.6667 | [-26.6667, 19.6667] | 6 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |

### Kind: personalized

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | — | — | — | — | 0 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 30 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 30 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.4000 | 0.5667 | +0.1667 | [-0.1333, 0.4667] | 30 |
|  | McNemar: b=8.0, c=13.0, p=1.000 | | | | |
| reflections | 0.0000 | 0.4333 | +0.4333 | [0.2667, 0.6000] | 30 |
| llm_latency_seconds | 5.9833 | 7.4130 | +1.4297 | [0.2256, 2.6434] | 30 |
| completion_tokens | 346.0000 | 457.9000 | +111.9000 | [17.5667, 208.0333] | 30 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 10 |
| inference_latency_seconds | 3.2870 | 5.8217 | +2.5347 | [0.5779, 4.3290] | 30 |
| inference_completion_tokens | 304.7333 | 579.8333 | +275.1000 | [88.6000, 441.3000] | 30 |

### Kind: similar

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 30 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 30 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 30 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 30 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 30 |
| llm_latency_seconds | 4.4252 | 4.1901 | -0.2351 | [-0.8315, 0.3503] | 30 |
| completion_tokens | 154.5333 | 159.0000 | +4.4667 | [-6.8000, 15.9000] | 30 |
| answer_fallback | 0.0333 | 0.0000 | -0.0333 | [-0.1000, 0.0000] | 30 |
| inference_latency_seconds | 13.5927 | 10.1771 | -3.4156 | [-6.2114, -0.9817] | 30 |
| inference_completion_tokens | 1160.8000 | 989.9667 | -170.8333 | [-343.3667, 8.4667] | 30 |

## Results by Kind × Segment

### ambiguous / none

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| recall@10 | — | — | — | — | 0 |
| ndcg@10 | — | — | — | — | 0 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| llm_latency_seconds | 3.2475 | 3.8465 | +0.5990 | [-0.2083, 1.8413] | 6 |
| completion_tokens | 95.6667 | 92.0000 | -3.6667 | [-26.6667, 19.6667] | 6 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |

### personalized / sparse

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | — | — | — | — | 0 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.4667 | 0.4000 | -0.0667 | [-0.4667, 0.3333] | 15 |
|  | McNemar: b=6.0, c=5.0, p=1.000 | | | | |
| reflections | 0.0000 | 0.6000 | +0.6000 | [0.3333, 0.8667] | 15 |
| llm_latency_seconds | 6.3999 | 8.5751 | +2.1751 | [0.2761, 4.0192] | 15 |
| completion_tokens | 346.8000 | 557.3333 | +210.5333 | [78.4000, 341.2000] | 15 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| inference_latency_seconds | 4.0459 | 6.9279 | +2.8820 | [-0.4887, 5.6706] | 15 |
| inference_completion_tokens | 361.7333 | 683.9333 | +322.2000 | [5.8667, 574.3333] | 15 |

### personalized / warm

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | — | — | — | — | 0 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.3333 | 0.7333 | +0.4000 | [0.0000, 0.7333] | 15 |
|  | McNemar: b=2.0, c=8.0, p=1.000 | | | | |
| reflections | 0.0000 | 0.2667 | +0.2667 | [0.0667, 0.5333] | 15 |
| llm_latency_seconds | 5.5667 | 6.2510 | +0.6843 | [-0.6731, 2.2228] | 15 |
| completion_tokens | 345.2000 | 358.4667 | +13.2667 | [-94.0000, 137.4667] | 15 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 4 |
| inference_latency_seconds | 2.5281 | 4.7155 | +2.1874 | [-0.0918, 4.1811] | 15 |
| inference_completion_tokens | 247.7333 | 475.7333 | +228.0000 | [7.5333, 432.5333] | 15 |

### similar / sparse

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| llm_latency_seconds | 4.4157 | 4.0229 | -0.3927 | [-1.0093, 0.1365] | 15 |
| completion_tokens | 144.7333 | 159.4000 | +14.6667 | [0.6000, 29.2000] | 15 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| inference_latency_seconds | 14.0927 | 9.9167 | -4.1760 | [-9.3739, 0.0387] | 15 |
| inference_completion_tokens | 1170.7333 | 1006.0000 | -164.7333 | [-435.6000, 122.5333] | 15 |

### similar / warm

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| llm_latency_seconds | 4.4347 | 4.3573 | -0.0774 | [-1.1607, 0.9019] | 15 |
| completion_tokens | 164.3333 | 158.6000 | -5.7333 | [-21.9333, 9.3333] | 15 |
| answer_fallback | 0.0667 | 0.0000 | -0.0667 | [-0.2000, 0.0000] | 15 |
| inference_latency_seconds | 13.0927 | 10.4375 | -2.6553 | [-5.0239, -0.0701] | 15 |
| inference_completion_tokens | 1150.8667 | 973.9333 | -176.9333 | [-404.5333, 26.7333] | 15 |
