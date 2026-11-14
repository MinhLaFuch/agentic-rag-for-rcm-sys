# Ablation Comparison: reflect_effect_planner

**Agent A:** planner (group: planner_tmpl_r0)
**Agent B:** planner (group: planner_tmpl_r1)
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
| llm_latency_seconds | 6.0600 | 6.4245 | +0.3645 | [-0.5907, 1.3505] | 6 |
| completion_tokens | 28.8333 | 32.8333 | +4.0000 | [-1.5000, 10.3333] | 6 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |

### Kind: exclusion

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.9500 | 0.9250 | -0.0250 | [-0.1250, 0.0750] | 40 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 21 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 21 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.9500 | 0.9750 | +0.0250 | [-0.0500, 0.1000] | 40 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| llm_latency_seconds | 19.2988 | 18.4254 | -0.8735 | [-2.8208, 0.9936] | 40 |
| completion_tokens | 529.6500 | 466.9250 | -62.7250 | [-137.6000, 8.2000] | 40 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 35 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |

### Kind: personalized

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | — | — | — | — | 0 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.7500 | 0.5000 | -0.2500 | [-0.4500, -0.0500] | 40 |
|  | McNemar: b=14.0, c=4.0, p=0.050 | | | | |
| reflections | 0.0000 | 0.5000 | +0.5000 | [0.3500, 0.6500] | 40 |
| llm_latency_seconds | 10.6715 | 17.4613 | +6.7898 | [4.2760, 9.7665] | 40 |
| completion_tokens | 184.0500 | 301.9000 | +117.8500 | [73.1250, 163.9250] | 40 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 27 |
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
| llm_latency_seconds | 9.1986 | 8.4001 | -0.7985 | [-1.5075, -0.1336] | 40 |
| completion_tokens | 116.7000 | 117.5250 | +0.8250 | [-1.5000, 3.4000] | 40 |
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
| llm_latency_seconds | 9.3045 | 14.3207 | +5.0162 | [3.6337, 6.4458] | 6 |
| completion_tokens | 104.3333 | 183.5000 | +79.1667 | [29.3333, 132.1667] | 6 |
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
| llm_latency_seconds | 6.0600 | 6.4245 | +0.3645 | [-0.5907, 1.3505] | 6 |
| completion_tokens | 28.8333 | 32.8333 | +4.0000 | [-1.5000, 10.3333] | 6 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |

### exclusion / sparse

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.9500 | 0.9000 | -0.0500 | [-0.2000, 0.1000] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 13 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 13 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.9500 | 0.9500 | +0.0000 | [-0.1500, 0.1500] | 20 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| llm_latency_seconds | 19.2156 | 19.3453 | +0.1297 | [-2.4873, 2.6053] | 20 |
| completion_tokens | 509.7500 | 512.9000 | +3.1500 | [-102.2500, 100.4000] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 17 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |

### exclusion / warm

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.9500 | 0.9500 | +0.0000 | [-0.1500, 0.1500] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 8 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 8 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.9500 | 1.0000 | +0.0500 | [0.0000, 0.1500] | 20 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| llm_latency_seconds | 19.3821 | 17.5054 | -1.8767 | [-4.5367, 0.9819] | 20 |
| completion_tokens | 549.5500 | 420.9500 | -128.6000 | [-226.9500, -39.6500] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 18 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |

### personalized / sparse

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | — | — | — | — | 0 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.8000 | 0.6500 | -0.1500 | [-0.4500, 0.1500] | 20 |
| reflections | 0.0000 | 0.3500 | +0.3500 | [0.1500, 0.5500] | 20 |
| llm_latency_seconds | 11.2000 | 16.5133 | +5.3133 | [1.7492, 10.4617] | 20 |
| completion_tokens | 191.5000 | 249.5000 | +58.0000 | [12.0500, 106.4000] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |

### personalized / warm

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | — | — | — | — | 0 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.7000 | 0.3500 | -0.3500 | [-0.6000, -0.1000] | 20 |
| reflections | 0.0000 | 0.6500 | +0.6500 | [0.4500, 0.8500] | 20 |
| llm_latency_seconds | 10.1429 | 18.4092 | +8.2663 | [5.3608, 11.2891] | 20 |
| completion_tokens | 176.6000 | 354.3000 | +177.7000 | [111.1000, 243.8500] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 12 |
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
| llm_latency_seconds | 8.6838 | 8.0305 | -0.6533 | [-1.3502, -0.0110] | 20 |
| completion_tokens | 116.5500 | 115.3000 | -1.2500 | [-4.5000, 1.7500] | 20 |
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
| llm_latency_seconds | 9.7134 | 8.7697 | -0.9436 | [-2.2085, 0.2281] | 20 |
| completion_tokens | 116.8500 | 119.7500 | +2.9000 | [-0.2500, 6.9500] | 20 |
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
| llm_latency_seconds | 9.3045 | 14.3207 | +5.0162 | [3.6337, 6.4458] | 6 |
| completion_tokens | 104.3333 | 183.5000 | +79.1667 | [29.3333, 132.1667] | 6 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
