# Ablation Comparison: memory_effect_reflect1

**Agent A:** planner (group: planner_tmpl_r1)
**Agent B:** planner_memory (group: pmem_tmpl_r1)
**Bootstrap resamples:** 10000
**Confidence level:** 95.0%
**k:** 10

**Number of paired requests:** 132

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
| llm_latency_seconds | 6.4245 | 5.4532 | -0.9713 | [-1.9217, -0.2790] | 6 |
| completion_tokens | 32.8333 | 29.5000 | -3.3333 | [-9.6667, 1.1667] | 6 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |

### Kind: exclusion

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.9250 | 0.9500 | +0.0250 | [-0.0750, 0.1250] | 40 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 21 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 21 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.9750 | 0.7000 | -0.2750 | [-0.4250, -0.1250] | 40 |
|  | McNemar: b=12.0, c=1.0, p=0.010 | | | | |
| reflections | 0.0000 | 0.2750 | +0.2750 | [0.1500, 0.4250] | 40 |
| llm_latency_seconds | 18.4254 | 26.2128 | +7.7874 | [4.7031, 11.0308] | 40 |
| completion_tokens | 466.9250 | 704.0250 | +237.1000 | [168.6750, 310.5000] | 40 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 35 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |

### Kind: similar

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| recall@10 | 0.0063 | 0.0063 | +0.0000 | [0.0000, 0.0000] | 40 |
| ndcg@10 | 0.0062 | 0.0062 | +0.0000 | [0.0000, 0.0000] | 40 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| llm_latency_seconds | 8.4001 | 7.5562 | -0.8439 | [-1.2491, -0.4665] | 40 |
| completion_tokens | 117.5250 | 120.3750 | +2.8500 | [-0.6250, 6.5000] | 40 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |

### Kind: unanswerable

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| recall@10 | — | — | — | — | 0 |
| ndcg@10 | — | — | — | — | 0 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| reflections | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| llm_latency_seconds | 14.3207 | 13.3487 | -0.9720 | [-2.1778, 0.7155] | 6 |
| completion_tokens | 183.5000 | 160.0000 | -23.5000 | [-81.3333, 50.0000] | 6 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |

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
| llm_latency_seconds | 6.4245 | 5.4532 | -0.9713 | [-1.9217, -0.2790] | 6 |
| completion_tokens | 32.8333 | 29.5000 | -3.3333 | [-9.6667, 1.1667] | 6 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |

### exclusion / sparse

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.9000 | 0.9000 | +0.0000 | [-0.2000, 0.2000] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 13 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 13 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.9500 | 0.6000 | -0.3500 | [-0.6000, -0.1000] | 20 |
| reflections | 0.0000 | 0.3500 | +0.3500 | [0.1500, 0.5500] | 20 |
| llm_latency_seconds | 19.3453 | 23.9953 | +4.6500 | [2.2094, 6.9280] | 20 |
| completion_tokens | 512.9000 | 713.5500 | +200.6500 | [122.9500, 281.1000] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 16 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |

### exclusion / warm

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.9500 | 1.0000 | +0.0500 | [0.0000, 0.1500] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 8 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 8 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 0.8000 | -0.2000 | [-0.4000, -0.0500] | 20 |
| reflections | 0.0000 | 0.2000 | +0.2000 | [0.0500, 0.4000] | 20 |
| llm_latency_seconds | 17.5054 | 28.4303 | +10.9249 | [5.3116, 16.4827] | 20 |
| completion_tokens | 420.9500 | 694.5000 | +273.5500 | [161.5000, 391.2500] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 19 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |

### similar / sparse

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| recall@10 | 0.0125 | 0.0125 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0123 | 0.0123 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| llm_latency_seconds | 8.0305 | 7.5046 | -0.5259 | [-0.8929, -0.1624] | 20 |
| completion_tokens | 115.3000 | 121.4000 | +6.1000 | [1.5000, 11.7000] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |

### similar / warm

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| llm_latency_seconds | 8.7697 | 7.6078 | -1.1619 | [-1.8097, -0.5079] | 20 |
| completion_tokens | 119.7500 | 119.3500 | -0.4000 | [-4.9500, 3.7500] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |

### unanswerable / none

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| recall@10 | — | — | — | — | 0 |
| ndcg@10 | — | — | — | — | 0 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| reflections | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| llm_latency_seconds | 14.3207 | 13.3487 | -0.9720 | [-2.1778, 0.7155] | 6 |
| completion_tokens | 183.5000 | 160.0000 | -23.5000 | [-81.3333, 50.0000] | 6 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
