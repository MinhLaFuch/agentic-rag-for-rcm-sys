# Ablation Comparison: baseline_vs_full_agent

**Agent A:** baseline (group: baseline_itemknn)
**Agent B:** planner_memory (group: pmem_tmpl_r1)
**Bootstrap resamples:** 10000
**Confidence level:** 95.0%
**k:** 10

**Number of paired requests:** 120

**Variance:** Only 1 run per group, cannot compute variance

## Results by Kind (aggregated across segments)

### Kind: exclusion

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 0.9500 | -0.0500 | [-0.1250, 0.0000] | 40 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 21 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 21 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | — | — | — | — | 0 |
| reflections | — | — | — | — | 0 |
| llm_latency_seconds | — | — | — | — | 0 |
| completion_tokens | — | — | — | — | 0 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | — | — | — | — | 0 |
| inference_completion_tokens | — | — | — | — | 0 |

### Kind: personalized

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | — | — | — | — | 0 |
| reflections | — | — | — | — | 0 |
| llm_latency_seconds | — | — | — | — | 0 |
| completion_tokens | — | — | — | — | 0 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | — | — | — | — | 0 |
| inference_completion_tokens | — | — | — | — | 0 |

### Kind: similar

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| recall@10 | 0.0063 | 0.0063 | +0.0000 | [0.0000, 0.0000] | 40 |
| ndcg@10 | 0.0062 | 0.0062 | +0.0000 | [0.0000, 0.0000] | 40 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | — | — | — | — | 0 |
| reflections | — | — | — | — | 0 |
| llm_latency_seconds | — | — | — | — | 0 |
| completion_tokens | — | — | — | — | 0 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | — | — | — | — | 0 |
| inference_completion_tokens | — | — | — | — | 0 |

## Results by Kind × Segment

### exclusion / sparse

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 0.9000 | -0.1000 | [-0.2500, 0.0000] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 13 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 13 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | — | — | — | — | 0 |
| reflections | — | — | — | — | 0 |
| llm_latency_seconds | — | — | — | — | 0 |
| completion_tokens | — | — | — | — | 0 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | — | — | — | — | 0 |
| inference_completion_tokens | — | — | — | — | 0 |

### exclusion / warm

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 8 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 8 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | — | — | — | — | 0 |
| reflections | — | — | — | — | 0 |
| llm_latency_seconds | — | — | — | — | 0 |
| completion_tokens | — | — | — | — | 0 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | — | — | — | — | 0 |
| inference_completion_tokens | — | — | — | — | 0 |

### personalized / sparse

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | — | — | — | — | 0 |
| reflections | — | — | — | — | 0 |
| llm_latency_seconds | — | — | — | — | 0 |
| completion_tokens | — | — | — | — | 0 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | — | — | — | — | 0 |
| inference_completion_tokens | — | — | — | — | 0 |

### personalized / warm

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | — | — | — | — | 0 |
| reflections | — | — | — | — | 0 |
| llm_latency_seconds | — | — | — | — | 0 |
| completion_tokens | — | — | — | — | 0 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | — | — | — | — | 0 |
| inference_completion_tokens | — | — | — | — | 0 |

### similar / sparse

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| recall@10 | 0.0125 | 0.0125 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0123 | 0.0123 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | — | — | — | — | 0 |
| reflections | — | — | — | — | 0 |
| llm_latency_seconds | — | — | — | — | 0 |
| completion_tokens | — | — | — | — | 0 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | — | — | — | — | 0 |
| inference_completion_tokens | — | — | — | — | 0 |

### similar / warm

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | — | — | — | — | 0 |
| reflections | — | — | — | — | 0 |
| llm_latency_seconds | — | — | — | — | 0 |
| completion_tokens | — | — | — | — | 0 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | — | — | — | — | 0 |
| inference_completion_tokens | — | — | — | — | 0 |
