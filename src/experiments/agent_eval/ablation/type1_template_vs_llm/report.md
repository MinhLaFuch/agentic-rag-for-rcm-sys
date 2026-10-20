# Ablation Comparison: type1_template_vs_llm

**Agent A:** type1 (group: infer_template)
**Agent B:** type1 (group: reflect_1)
**Bootstrap resamples:** 10000
**Confidence level:** 95.0%
**k:** 10

**Number of paired requests:** 40

**Variance:** Only 1 run per group, cannot compute variance

## Results by Kind (aggregated across segments)

### Kind: similar

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
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| inference_latency_seconds | 0.0000 | 12.8375 | +12.8375 | [11.1758, 14.7406] | 40 |
| inference_completion_tokens | 0.0000 | 829.0000 | +829.0000 | [752.5750, 912.8250] | 40 |

## Results by Kind × Segment

### similar / sparse

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
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_latency_seconds | 0.0000 | 12.6384 | +12.6384 | [10.4557, 15.4198] | 20 |
| inference_completion_tokens | 0.0000 | 795.2000 | +795.2000 | [706.6000, 901.6000] | 20 |

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
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_latency_seconds | 0.0000 | 13.0366 | +13.0366 | [10.6350, 15.8077] | 20 |
| inference_completion_tokens | 0.0000 | 862.8000 | +862.8000 | [741.0000, 997.2000] | 20 |
