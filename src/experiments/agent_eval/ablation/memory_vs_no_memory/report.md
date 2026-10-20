# Ablation Comparison: memory_vs_no_memory

**Agent A:** planner (group: reflect_1)
**Agent B:** planner_memory (group: reflect_1)
**Bootstrap resamples:** 10000
**Confidence level:** 95.0%
**k:** 10

**Number of paired requests:** 146

**Variance:** Only 1 run per group, cannot compute variance

## Results by Kind (aggregated across segments)

### Kind: cold_text
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.8500 | 0.9000 | +0.0500 | [0.0000, 0.1500] | 20 |
| recall@10 | 0.0417 | 0.1917 | +0.1500 | [0.0000, 0.3000] | 20 |
| ndcg@10 | 0.0384 | 0.0963 | +0.0579 | [0.0018, 0.1246] | 20 |
| constraint_satisfaction | 0.8500 | 0.9000 | +0.0500 | [0.0000, 0.1500] | 20 |
| first_attempt_ok | 0.8500 | 0.8000 | -0.0500 | [-0.2000, 0.1000] | 20 |
| reflections | 0.0500 | 0.1000 | +0.0500 | [-0.1000, 0.2000] | 20 |
| llm_latency_seconds | 6.7532 | 7.4010 | +0.6478 | [-1.8280, 3.5423] | 20 |
| completion_tokens | 161.8500 | 137.8500 | -24.0000 | [-55.8500, 14.9500] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 17 |
| inference_latency_seconds | 11.1328 | 11.8016 | +0.6688 | [-2.4500, 4.0993] | 20 |
| inference_completion_tokens | 735.3500 | 777.7500 | +42.4000 | [-157.6000, 238.8500] | 20 |

### Kind: constrained
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.8750 | 0.8750 | +0.0000 | [-0.1250, 0.1500] | 40 |
| recall@10 | 0.1750 | 0.1750 | +0.0000 | [-0.1250, 0.1250] | 40 |
| ndcg@10 | 0.0998 | 0.0887 | -0.0111 | [-0.0802, 0.0527] | 40 |
| constraint_satisfaction | 0.9450 | 0.8750 | -0.0700 | [-0.1825, 0.0400] | 40 |
| first_attempt_ok | 1.0000 | 0.9500 | -0.0500 | [-0.1250, 0.0000] | 40 |
| reflections | 0.0000 | 0.0250 | +0.0250 | [0.0000, 0.0750] | 40 |
| llm_latency_seconds | 6.8157 | 7.5645 | +0.7488 | [-1.0239, 3.1311] | 40 |
| completion_tokens | 180.5000 | 157.0250 | -23.4750 | [-40.6750, -5.3000] | 40 |
| answer_fallback | 0.0000 | 0.0526 | +0.0526 | [0.0000, 0.1316] | 38 |
| inference_latency_seconds | 11.0184 | 12.1289 | +1.1105 | [-0.8194, 3.1136] | 40 |
| inference_completion_tokens | 690.3000 | 792.4250 | +102.1250 | [2.7000, 204.3500] | 40 |

### Kind: similar

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 0.9750 | -0.0250 | [-0.0750, 0.0000] | 40 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 0.9750 | -0.0250 | [-0.0750, 0.0000] | 40 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| llm_latency_seconds | 12.2785 | 12.9644 | +0.6859 | [-6.2848, 9.4414] | 40 |
| completion_tokens | 572.1000 | 535.6750 | -36.4250 | [-149.8250, 74.0500] | 40 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 39 |
| inference_latency_seconds | 21.9173 | 18.3610 | -3.5563 | [-7.4762, 0.4677] | 40 |
| inference_completion_tokens | 971.3750 | 988.7250 | +17.3500 | [-82.6500, 122.3250] | 40 |

## Results by Kind × Segment

### cold_text / cold
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.8500 | 0.9000 | +0.0500 | [0.0000, 0.1500] | 20 |
| recall@10 | 0.0417 | 0.1917 | +0.1500 | [0.0000, 0.3000] | 20 |
| ndcg@10 | 0.0384 | 0.0963 | +0.0579 | [0.0018, 0.1246] | 20 |
| constraint_satisfaction | 0.8500 | 0.9000 | +0.0500 | [0.0000, 0.1500] | 20 |
| first_attempt_ok | 0.8500 | 0.8000 | -0.0500 | [-0.2000, 0.1000] | 20 |
| reflections | 0.0500 | 0.1000 | +0.0500 | [-0.1000, 0.2000] | 20 |
| llm_latency_seconds | 6.7532 | 7.4010 | +0.6478 | [-1.8280, 3.5423] | 20 |
| completion_tokens | 161.8500 | 137.8500 | -24.0000 | [-55.8500, 14.9500] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 17 |
| inference_latency_seconds | 11.1328 | 11.8016 | +0.6688 | [-2.4500, 4.0993] | 20 |
| inference_completion_tokens | 735.3500 | 777.7500 | +42.4000 | [-157.6000, 238.8500] | 20 |

### constrained / sparse
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.8500 | 0.9500 | +0.1000 | [0.0000, 0.2500] | 20 |
| recall@10 | 0.2500 | 0.2000 | -0.0500 | [-0.2500, 0.1500] | 20 |
| ndcg@10 | 0.1588 | 0.1216 | -0.0372 | [-0.1759, 0.0787] | 20 |
| constraint_satisfaction | 0.9550 | 0.9500 | -0.0050 | [-0.0700, 0.0500] | 20 |
| first_attempt_ok | 1.0000 | 0.9500 | -0.0500 | [-0.1500, 0.0000] | 20 |
| reflections | 0.0000 | 0.0500 | +0.0500 | [0.0000, 0.1500] | 20 |
| llm_latency_seconds | 6.9752 | 6.5532 | -0.4220 | [-1.6071, 0.9129] | 20 |
| completion_tokens | 184.4000 | 165.7500 | -18.6500 | [-37.8000, 5.3000] | 20 |
| answer_fallback | 0.0000 | 0.1000 | +0.1000 | [0.0000, 0.2500] | 20 |
| inference_latency_seconds | 11.0421 | 13.4765 | +2.4344 | [-0.3274, 5.4201] | 20 |
| inference_completion_tokens | 712.4000 | 829.5000 | +117.1000 | [-24.0000, 267.4000] | 20 |

### constrained / warm
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.9000 | 0.8000 | -0.1000 | [-0.3500, 0.1500] | 20 |
| recall@10 | 0.1000 | 0.1500 | +0.0500 | [0.0000, 0.1500] | 20 |
| ndcg@10 | 0.0408 | 0.0558 | +0.0151 | [-0.0022, 0.0473] | 20 |
| constraint_satisfaction | 0.9350 | 0.8000 | -0.1350 | [-0.3500, 0.0650] | 20 |
| first_attempt_ok | 1.0000 | 0.9500 | -0.0500 | [-0.1500, 0.0000] | 20 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| llm_latency_seconds | 6.6562 | 8.5758 | +1.9196 | [-1.2014, 6.4632] | 20 |
| completion_tokens | 176.6000 | 148.3000 | -28.3000 | [-56.4500, -0.7000] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 18 |
| inference_latency_seconds | 10.9946 | 10.7812 | -0.2134 | [-2.6471, 2.3491] | 20 |
| inference_completion_tokens | 668.2000 | 755.3500 | +87.1500 | [-49.5000, 224.0500] | 20 |

### similar / sparse

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 0.9500 | -0.0500 | [-0.1500, 0.0000] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 0.9500 | -0.0500 | [-0.1500, 0.0000] | 20 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| llm_latency_seconds | 10.2774 | 16.7186 | +6.4412 | [-0.9534, 20.1639] | 20 |
| completion_tokens | 685.9500 | 641.1000 | -44.8500 | [-189.1500, 95.5000] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 19 |
| inference_latency_seconds | 23.2251 | 21.4132 | -1.8119 | [-8.8956, 5.2059] | 20 |
| inference_completion_tokens | 1022.4000 | 1018.9000 | -3.5000 | [-161.1000, 141.1500] | 20 |

### similar / warm

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| llm_latency_seconds | 14.2796 | 9.2101 | -5.0695 | [-14.1508, 0.3959] | 20 |
| completion_tokens | 458.2500 | 430.2500 | -28.0000 | [-202.1000, 134.7000] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_latency_seconds | 20.6094 | 15.3087 | -5.3007 | [-9.0444, -2.1334] | 20 |
| inference_completion_tokens | 920.3500 | 958.5500 | +38.2000 | [-68.1000, 184.0000] | 20 |
