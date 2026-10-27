# Ablation Comparison: memory_vs_no_memory

**Agent A:** planner (group: reflect_1)
**Agent B:** planner_memory (group: reflect_1)
**Bootstrap resamples:** 10000
**Confidence level:** 95.0%
**k:** 10

**Number of paired requests:** 66

**Variance:** Only 1 run per group, cannot compute variance

## Results by Kind (aggregated across segments)

### Kind: similar

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 30 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 30 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 30 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 30 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 30 |
| llm_latency_seconds | 4.1901 | 5.2203 | +1.0302 | [-0.5883, 3.7630] | 30 |
| completion_tokens | 159.0000 | 168.0000 | +9.0000 | [-4.7000, 22.9000] | 30 |
| answer_fallback | 0.0000 | 0.0333 | +0.0333 | [0.0000, 0.1000] | 30 |
| inference_latency_seconds | 10.1771 | 12.6802 | +2.5031 | [0.3042, 4.4698] | 30 |
| inference_completion_tokens | 989.9667 | 1159.5000 | +169.5333 | [-45.4000, 374.4333] | 30 |

## Results by Kind × Segment

### similar / sparse

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| llm_latency_seconds | 4.0229 | 4.0897 | +0.0668 | [-0.6760, 0.7573] | 15 |
| completion_tokens | 159.4000 | 162.3333 | +2.9333 | [-14.7333, 19.0000] | 15 |
| answer_fallback | 0.0000 | 0.0667 | +0.0667 | [0.0000, 0.2000] | 15 |
| inference_latency_seconds | 9.9167 | 13.4989 | +3.5823 | [1.3875, 5.6542] | 15 |
| inference_completion_tokens | 1006.0000 | 1168.0667 | +162.0667 | [-133.8000, 444.2667] | 15 |

### similar / warm

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| llm_latency_seconds | 4.3573 | 6.3509 | +1.9937 | [-1.0395, 7.2697] | 15 |
| completion_tokens | 158.6000 | 173.6667 | +15.0667 | [-4.7333, 37.6667] | 15 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| inference_latency_seconds | 10.4375 | 11.8615 | +1.4240 | [-2.3153, 4.6526] | 15 |
| inference_completion_tokens | 973.9333 | 1150.9333 | +177.0000 | [-146.9333, 469.5333] | 15 |
