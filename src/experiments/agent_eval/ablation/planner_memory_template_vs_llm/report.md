# Ablation Comparison: planner_memory_template_vs_llm

**Agent A:** planner_memory (group: infer_template)
**Agent B:** planner_memory (group: reflect_1)
**Bootstrap resamples:** 10000
**Confidence level:** 95.0%
**k:** 10

**Number of paired requests:** 146

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
| llm_latency_seconds | 11.4400 | 13.7343 | +2.2943 | [-12.2755, 21.7240] | 6 |
| completion_tokens | 28.1667 | 34.0000 | +5.8333 | [-4.0000, 15.6667] | 6 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |

### Kind: cold_text
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 0.9000 | -0.1000 | [-0.2500, 0.0000] | 20 |
| recall@10 | 0.0917 | 0.1917 | +0.1000 | [0.0000, 0.2500] | 20 |
| ndcg@10 | 0.0617 | 0.0963 | +0.0346 | [0.0000, 0.0811] | 20 |
| constraint_satisfaction | 1.0000 | 0.9000 | -0.1000 | [-0.2500, 0.0000] | 20 |
| first_attempt_ok | 1.0000 | 0.8000 | -0.2000 | [-0.4000, -0.0500] | 20 |
| reflections | 0.0000 | 0.1000 | +0.1000 | [0.0000, 0.2500] | 20 |
| llm_latency_seconds | 11.1539 | 7.4010 | -3.7530 | [-6.5874, -0.4709] | 20 |
| completion_tokens | 153.0000 | 137.8500 | -15.1500 | [-48.5500, 24.2500] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 18 |
| inference_latency_seconds | 0.0000 | 11.8016 | +11.8016 | [9.0281, 14.7992] | 20 |
| inference_completion_tokens | 0.0000 | 777.7500 | +777.7500 | [608.7500, 944.4000] | 20 |

### Kind: constrained
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 0.8750 | -0.1250 | [-0.2250, -0.0250] | 40 |
| recall@10 | 0.2500 | 0.1750 | -0.0750 | [-0.1750, 0.0250] | 40 |
| ndcg@10 | 0.1438 | 0.0887 | -0.0551 | [-0.1272, 0.0015] | 40 |
| constraint_satisfaction | 1.0000 | 0.8750 | -0.1250 | [-0.2250, -0.0250] | 40 |
| first_attempt_ok | 1.0000 | 0.9500 | -0.0500 | [-0.1250, 0.0000] | 40 |
| reflections | 0.0000 | 0.0250 | +0.0250 | [0.0000, 0.0750] | 40 |
| llm_latency_seconds | 10.1384 | 7.5645 | -2.5739 | [-4.7516, 0.1064] | 40 |
| completion_tokens | 172.5250 | 157.0250 | -15.5000 | [-29.6000, 0.1000] | 40 |
| answer_fallback | 0.0000 | 0.0513 | +0.0513 | [0.0000, 0.1282] | 39 |
| inference_latency_seconds | 0.0000 | 12.1289 | +12.1289 | [10.4339, 14.0174] | 40 |
| inference_completion_tokens | 0.0000 | 792.4250 | +792.4250 | [706.3000, 886.7000] | 40 |

### Kind: personalized

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.9750 | 0.6500 | -0.3250 | [-0.5000, -0.1750] | 40 |
|  | McNemar: b=14.0, c=1.0, p=0.010 | | | | |
| reflections | 0.0250 | 0.3500 | +0.3250 | [0.1750, 0.5000] | 40 |
| llm_latency_seconds | 6.5750 | 19.6085 | +13.0335 | [7.1697, 20.9626] | 40 |
| completion_tokens | 141.1500 | 281.1250 | +139.9750 | [74.0000, 242.0250] | 40 |
| answer_fallback | 0.0000 | 0.0500 | +0.0500 | [0.0000, 0.1250] | 40 |
| inference_latency_seconds | 0.0000 | 25.7168 | +25.7168 | [18.8319, 35.3773] | 40 |
| inference_completion_tokens | 0.0000 | 1152.0250 | +1152.0250 | [986.6500, 1326.5250] | 40 |

### Kind: similar

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 0.9750 | -0.0250 | [-0.0750, 0.0000] | 40 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 0.9750 | -0.0250 | [-0.0750, 0.0000] | 40 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| llm_latency_seconds | 6.9517 | 12.9644 | +6.0127 | [2.2677, 12.8368] | 40 |
| completion_tokens | 131.1250 | 535.6750 | +404.5500 | [313.3000, 491.3500] | 40 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 39 |
| inference_latency_seconds | 0.0000 | 18.3610 | +18.3610 | [15.5828, 21.7344] | 40 |
| inference_completion_tokens | 0.0000 | 988.7250 | +988.7250 | [865.3250, 1131.6500] | 40 |

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
| llm_latency_seconds | 11.4400 | 13.7343 | +2.2943 | [-12.2755, 21.7240] | 6 |
| completion_tokens | 28.1667 | 34.0000 | +5.8333 | [-4.0000, 15.6667] | 6 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |

### cold_text / cold
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 0.9000 | -0.1000 | [-0.2500, 0.0000] | 20 |
| recall@10 | 0.0917 | 0.1917 | +0.1000 | [0.0000, 0.2500] | 20 |
| ndcg@10 | 0.0617 | 0.0963 | +0.0346 | [0.0000, 0.0811] | 20 |
| constraint_satisfaction | 1.0000 | 0.9000 | -0.1000 | [-0.2500, 0.0000] | 20 |
| first_attempt_ok | 1.0000 | 0.8000 | -0.2000 | [-0.4000, -0.0500] | 20 |
| reflections | 0.0000 | 0.1000 | +0.1000 | [0.0000, 0.2500] | 20 |
| llm_latency_seconds | 11.1539 | 7.4010 | -3.7530 | [-6.5874, -0.4709] | 20 |
| completion_tokens | 153.0000 | 137.8500 | -15.1500 | [-48.5500, 24.2500] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 18 |
| inference_latency_seconds | 0.0000 | 11.8016 | +11.8016 | [9.0281, 14.7992] | 20 |
| inference_completion_tokens | 0.0000 | 777.7500 | +777.7500 | [608.7500, 944.4000] | 20 |

### constrained / sparse
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 0.9500 | -0.0500 | [-0.1500, 0.0000] | 20 |
| recall@10 | 0.3500 | 0.2000 | -0.1500 | [-0.3000, 0.0000] | 20 |
| ndcg@10 | 0.2225 | 0.1216 | -0.1009 | [-0.2324, 0.0000] | 20 |
| constraint_satisfaction | 1.0000 | 0.9500 | -0.0500 | [-0.1500, 0.0000] | 20 |
| first_attempt_ok | 1.0000 | 0.9500 | -0.0500 | [-0.1500, 0.0000] | 20 |
| reflections | 0.0000 | 0.0500 | +0.0500 | [0.0000, 0.1500] | 20 |
| llm_latency_seconds | 10.3469 | 6.5532 | -3.7938 | [-6.5823, -1.4874] | 20 |
| completion_tokens | 176.4000 | 165.7500 | -10.6500 | [-34.2000, 16.4000] | 20 |
| answer_fallback | 0.0000 | 0.1000 | +0.1000 | [0.0000, 0.2500] | 20 |
| inference_latency_seconds | 0.0000 | 13.4765 | +13.4765 | [10.9555, 16.4508] | 20 |
| inference_completion_tokens | 0.0000 | 829.5000 | +829.5000 | [705.4500, 974.7000] | 20 |

### constrained / warm
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 0.8000 | -0.2000 | [-0.4000, -0.0500] | 20 |
| recall@10 | 0.1500 | 0.1500 | +0.0000 | [-0.1500, 0.1500] | 20 |
| ndcg@10 | 0.0651 | 0.0558 | -0.0092 | [-0.0750, 0.0473] | 20 |
| constraint_satisfaction | 1.0000 | 0.8000 | -0.2000 | [-0.4000, -0.0500] | 20 |
| first_attempt_ok | 1.0000 | 0.9500 | -0.0500 | [-0.1500, 0.0000] | 20 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| llm_latency_seconds | 9.9299 | 8.5758 | -1.3540 | [-4.3494, 3.3327] | 20 |
| completion_tokens | 168.6500 | 148.3000 | -20.3500 | [-36.7500, -2.9500] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 19 |
| inference_latency_seconds | 0.0000 | 10.7812 | +10.7812 | [8.7945, 12.9093] | 20 |
| inference_completion_tokens | 0.0000 | 755.3500 | +755.3500 | [638.1000, 865.2000] | 20 |

### personalized / sparse

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.9500 | 0.7000 | -0.2500 | [-0.5000, 0.0000] | 20 |
| reflections | 0.0500 | 0.3000 | +0.2500 | [0.0000, 0.5000] | 20 |
| llm_latency_seconds | 6.5860 | 26.0577 | +19.4717 | [9.3360, 33.1787] | 20 |
| completion_tokens | 145.1500 | 331.1500 | +186.0000 | [64.1000, 376.0500] | 20 |
| answer_fallback | 0.0000 | 0.1000 | +0.1000 | [0.0000, 0.2500] | 20 |
| inference_latency_seconds | 0.0000 | 34.7195 | +34.7195 | [22.2686, 51.8890] | 20 |
| inference_completion_tokens | 0.0000 | 1460.5500 | +1460.5500 | [1193.6000, 1710.2000] | 20 |

### personalized / warm

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 0.6000 | -0.4000 | [-0.6000, -0.2000] | 20 |
| reflections | 0.0000 | 0.4000 | +0.4000 | [0.2000, 0.6000] | 20 |
| llm_latency_seconds | 6.5640 | 13.1593 | +6.5953 | [2.9055, 11.7869] | 20 |
| completion_tokens | 137.1500 | 231.1000 | +93.9500 | [53.0500, 138.1500] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_latency_seconds | 0.0000 | 16.7141 | +16.7141 | [13.3196, 20.6165] | 20 |
| inference_completion_tokens | 0.0000 | 843.5000 | +843.5000 | [740.0500, 957.2500] | 20 |

### similar / sparse

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 0.9500 | -0.0500 | [-0.1500, 0.0000] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 0.9500 | -0.0500 | [-0.1500, 0.0000] | 20 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| llm_latency_seconds | 6.7408 | 16.7186 | +9.9779 | [2.9762, 22.9998] | 20 |
| completion_tokens | 131.3500 | 641.1000 | +509.7500 | [391.3500, 615.8500] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 19 |
| inference_latency_seconds | 0.0000 | 21.4132 | +21.4132 | [16.3329, 27.6811] | 20 |
| inference_completion_tokens | 0.0000 | 1018.9000 | +1018.9000 | [821.2000, 1235.2000] | 20 |

### similar / warm

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| llm_latency_seconds | 7.1626 | 9.2101 | +2.0475 | [0.9513, 3.1834] | 20 |
| completion_tokens | 130.9000 | 430.2500 | +299.3500 | [176.7000, 416.7500] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_latency_seconds | 0.0000 | 15.3087 | +15.3087 | [13.5471, 17.2377] | 20 |
| inference_completion_tokens | 0.0000 | 958.5500 | +958.5500 | [814.0500, 1143.6000] | 20 |
