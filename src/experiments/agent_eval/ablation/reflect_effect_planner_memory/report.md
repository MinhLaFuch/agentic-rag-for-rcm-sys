# Ablation Comparison: reflect_effect_planner_memory

**Agent A:** planner_memory (group: pmem_tmpl_r0)
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
| llm_latency_seconds | 6.6068 | 5.4532 | -1.1537 | [-2.1147, -0.2423] | 6 |
| completion_tokens | 34.0000 | 29.5000 | -4.5000 | [-13.6667, 4.3333] | 6 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |

### Kind: exclusion

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.8500 | 0.9500 | +0.1000 | [-0.0250, 0.2250] | 40 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 21 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 21 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.8750 | 0.7000 | -0.1750 | [-0.3750, 0.0250] | 40 |
|  | McNemar: b=12.0, c=5.0, p=1.000 | | | | |
| reflections | 0.0000 | 0.2750 | +0.2750 | [0.1500, 0.4250] | 40 |
| llm_latency_seconds | 30.3344 | 26.2128 | -4.1216 | [-8.9498, 0.6136] | 40 |
| completion_tokens | 727.4000 | 704.0250 | -23.3750 | [-108.1500, 67.3750] | 40 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 32 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |

### Kind: personalized

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.5500 | 1.0000 | +0.4500 | [0.3000, 0.6000] | 40 |
|  | McNemar: b=0.0, c=18.0, p=0.001 | | | | |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.5500 | 0.5750 | +0.0250 | [-0.2000, 0.2250] | 40 |
|  | McNemar: b=9.0, c=10.0, p=1.000 | | | | |
| reflections | 0.0000 | 0.4250 | +0.4250 | [0.2750, 0.5750] | 40 |
| llm_latency_seconds | 9.6505 | 12.8157 | +3.1652 | [1.7378, 4.6185] | 40 |
| completion_tokens | 191.4000 | 242.3250 | +50.9250 | [20.0250, 83.2250] | 40 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 22 |
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
| llm_latency_seconds | 8.1661 | 7.5562 | -0.6099 | [-1.4365, 0.0866] | 40 |
| completion_tokens | 121.1000 | 120.3750 | -0.7250 | [-4.4500, 2.6750] | 40 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |

### Kind: unanswerable

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.0000 | 1.0000 | +1.0000 | [1.0000, 1.0000] | 6 |
| recall@10 | — | — | — | — | 0 |
| ndcg@10 | — | — | — | — | 0 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| reflections | 0.0000 | 1.0000 | +1.0000 | [1.0000, 1.0000] | 6 |
| llm_latency_seconds | 6.7030 | 13.3487 | +6.6457 | [5.6478, 7.6902] | 6 |
| completion_tokens | 90.0000 | 160.0000 | +70.0000 | [41.1667, 115.1667] | 6 |
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
| llm_latency_seconds | 6.6068 | 5.4532 | -1.1537 | [-2.1147, -0.2423] | 6 |
| completion_tokens | 34.0000 | 29.5000 | -4.5000 | [-13.6667, 4.3333] | 6 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |

### exclusion / sparse

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.8000 | 0.9000 | +0.1000 | [-0.1500, 0.3500] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 13 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 13 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.8000 | 0.6000 | -0.2000 | [-0.5000, 0.1500] | 20 |
|  | McNemar: b=8.0, c=4.0, p=1.000 | | | | |
| reflections | 0.0000 | 0.3500 | +0.3500 | [0.1500, 0.5500] | 20 |
| llm_latency_seconds | 27.7142 | 23.9953 | -3.7189 | [-9.5158, 1.4140] | 20 |
| completion_tokens | 745.8500 | 713.5500 | -32.3000 | [-121.7500, 55.0500] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 14 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |

### exclusion / warm

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.9000 | 1.0000 | +0.1000 | [0.0000, 0.2500] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 8 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 8 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.9500 | 0.8000 | -0.1500 | [-0.3500, 0.0500] | 20 |
| reflections | 0.0000 | 0.2000 | +0.2000 | [0.0500, 0.4000] | 20 |
| llm_latency_seconds | 32.9547 | 28.4303 | -4.5244 | [-12.2729, 3.3373] | 20 |
| completion_tokens | 708.9500 | 694.5000 | -14.4500 | [-154.4000, 143.5000] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 18 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |

### personalized / sparse

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.6500 | 1.0000 | +0.3500 | [0.1500, 0.5500] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.6500 | 0.7500 | +0.1000 | [-0.2000, 0.4000] | 20 |
|  | McNemar: b=4.0, c=6.0, p=1.000 | | | | |
| reflections | 0.0000 | 0.2500 | +0.2500 | [0.1000, 0.4500] | 20 |
| llm_latency_seconds | 9.2105 | 11.2962 | +2.0857 | [0.1099, 4.1616] | 20 |
| completion_tokens | 174.2000 | 204.3000 | +30.1000 | [-11.4500, 75.1000] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 13 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |

### personalized / warm

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.4500 | 1.0000 | +0.5500 | [0.3500, 0.7500] | 20 |
|  | McNemar: b=0.0, c=11.0, p=0.010 | | | | |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.4500 | 0.4000 | -0.0500 | [-0.3500, 0.2500] | 20 |
| reflections | 0.0000 | 0.6000 | +0.6000 | [0.4000, 0.8000] | 20 |
| llm_latency_seconds | 10.0906 | 14.3352 | +4.2446 | [2.3164, 6.1579] | 20 |
| completion_tokens | 208.6000 | 280.3500 | +71.7500 | [29.7500, 116.1500] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 9 |
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
| llm_latency_seconds | 8.0946 | 7.5046 | -0.5900 | [-1.5907, 0.3459] | 20 |
| completion_tokens | 122.0000 | 121.4000 | -0.6000 | [-6.5000, 4.5500] | 20 |
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
| llm_latency_seconds | 8.2376 | 7.6078 | -0.6298 | [-1.9768, 0.3181] | 20 |
| completion_tokens | 120.2000 | 119.3500 | -0.8500 | [-5.9500, 3.5000] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |

### unanswerable / none

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.0000 | 1.0000 | +1.0000 | [1.0000, 1.0000] | 6 |
| recall@10 | — | — | — | — | 0 |
| ndcg@10 | — | — | — | — | 0 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| reflections | 0.0000 | 1.0000 | +1.0000 | [1.0000, 1.0000] | 6 |
| llm_latency_seconds | 6.7030 | 13.3487 | +6.6457 | [5.6478, 7.6902] | 6 |
| completion_tokens | 90.0000 | 160.0000 | +70.0000 | [41.1667, 115.1667] | 6 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
