# Ablation Comparison: planner_memory_reflect0_vs_reflect1

**Agent A:** planner_memory (group: reflect_0)
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
| llm_latency_seconds | 5.1483 | 13.7343 | +8.5860 | [-0.9558, 25.9380] | 6 |
| completion_tokens | 27.1667 | 34.0000 | +6.8333 | [-4.6667, 15.1667] | 6 |
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
| llm_latency_seconds | 8.3142 | 7.4010 | -0.9133 | [-3.4001, 2.0351] | 20 |
| completion_tokens | 154.7000 | 137.8500 | -16.8500 | [-51.9000, 24.4000] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 18 |
| inference_latency_seconds | 21.3991 | 11.8016 | -9.5975 | [-14.2985, -5.2989] | 20 |
| inference_completion_tokens | 849.5500 | 777.7500 | -71.8000 | [-267.9500, 121.9500] | 20 |

### Kind: constrained
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 0.8750 | -0.1250 | [-0.2250, -0.0250] | 40 |
| recall@10 | 0.2250 | 0.1750 | -0.0500 | [-0.1750, 0.0750] | 40 |
| ndcg@10 | 0.1313 | 0.0887 | -0.0426 | [-0.1190, 0.0232] | 40 |
| constraint_satisfaction | 1.0000 | 0.8750 | -0.1250 | [-0.2250, -0.0250] | 40 |
| first_attempt_ok | 1.0000 | 0.9500 | -0.0500 | [-0.1250, 0.0000] | 40 |
| reflections | 0.0000 | 0.0250 | +0.0250 | [0.0000, 0.0750] | 40 |
| llm_latency_seconds | 9.2075 | 7.5645 | -1.6430 | [-3.6284, 0.7801] | 40 |
| completion_tokens | 171.5000 | 157.0250 | -14.4750 | [-28.9000, 0.0250] | 40 |
| answer_fallback | 0.0513 | 0.0513 | +0.0000 | [-0.1026, 0.1026] | 39 |
| inference_latency_seconds | 19.8055 | 12.1289 | -7.6766 | [-9.9290, -5.4692] | 40 |
| inference_completion_tokens | 777.0500 | 792.4250 | +15.3750 | [-59.0000, 89.3000] | 40 |

### Kind: personalized

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 0.6500 | -0.3500 | [-0.5000, -0.2000] | 40 |
|  | McNemar: b=14.0, c=0.0, p=0.001 | | | | |
| reflections | 0.0000 | 0.3500 | +0.3500 | [0.2000, 0.5000] | 40 |
| llm_latency_seconds | 6.1551 | 19.6085 | +13.4533 | [7.5813, 21.2928] | 40 |
| completion_tokens | 141.9250 | 281.1250 | +139.2000 | [72.7750, 241.0000] | 40 |
| answer_fallback | 0.0000 | 0.0500 | +0.0500 | [0.0000, 0.1250] | 40 |
| inference_latency_seconds | 18.9202 | 25.7168 | +6.7966 | [-0.2917, 16.5835] | 40 |
| inference_completion_tokens | 796.7250 | 1152.0250 | +355.3000 | [188.2500, 531.4500] | 40 |

### Kind: similar

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 0.9750 | -0.0250 | [-0.0750, 0.0000] | 40 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 0.9750 | -0.0250 | [-0.0750, 0.0000] | 40 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| llm_latency_seconds | 6.7316 | 12.9644 | +6.2328 | [2.5624, 12.9749] | 40 |
| completion_tokens | 148.3500 | 535.6750 | +387.3250 | [297.8750, 473.8750] | 40 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 39 |
| inference_latency_seconds | 19.3966 | 18.3610 | -1.0356 | [-3.9314, 2.4030] | 40 |
| inference_completion_tokens | 807.2750 | 988.7250 | +181.4500 | [45.9500, 332.4750] | 40 |

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
| llm_latency_seconds | 5.1483 | 13.7343 | +8.5860 | [-0.9558, 25.9380] | 6 |
| completion_tokens | 27.1667 | 34.0000 | +6.8333 | [-4.6667, 15.1667] | 6 |
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
| llm_latency_seconds | 8.3142 | 7.4010 | -0.9133 | [-3.4001, 2.0351] | 20 |
| completion_tokens | 154.7000 | 137.8500 | -16.8500 | [-51.9000, 24.4000] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 18 |
| inference_latency_seconds | 21.3991 | 11.8016 | -9.5975 | [-14.2985, -5.2989] | 20 |
| inference_completion_tokens | 849.5500 | 777.7500 | -71.8000 | [-267.9500, 121.9500] | 20 |

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
| llm_latency_seconds | 9.4554 | 6.5532 | -2.9023 | [-4.8233, -1.1376] | 20 |
| completion_tokens | 171.0500 | 165.7500 | -5.3000 | [-23.8000, 17.6500] | 20 |
| answer_fallback | 0.0500 | 0.1000 | +0.0500 | [-0.1000, 0.2000] | 20 |
| inference_latency_seconds | 19.4413 | 13.4765 | -5.9647 | [-8.2497, -3.2952] | 20 |
| inference_completion_tokens | 804.5500 | 829.5000 | +24.9500 | [-45.5500, 100.6500] | 20 |

### constrained / warm
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 0.8000 | -0.2000 | [-0.4000, -0.0500] | 20 |
| recall@10 | 0.1000 | 0.1500 | +0.0500 | [-0.1000, 0.2000] | 20 |
| ndcg@10 | 0.0401 | 0.0558 | +0.0158 | [-0.0592, 0.0908] | 20 |
| constraint_satisfaction | 1.0000 | 0.8000 | -0.2000 | [-0.4000, -0.0500] | 20 |
| first_attempt_ok | 1.0000 | 0.9500 | -0.0500 | [-0.1500, 0.0000] | 20 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| llm_latency_seconds | 8.9595 | 8.5758 | -0.3837 | [-3.5557, 4.1420] | 20 |
| completion_tokens | 171.9500 | 148.3000 | -23.6500 | [-45.9500, -6.7500] | 20 |
| answer_fallback | 0.0526 | 0.0000 | -0.0526 | [-0.1579, 0.0000] | 19 |
| inference_latency_seconds | 20.1697 | 10.7812 | -9.3885 | [-12.9408, -5.9275] | 20 |
| inference_completion_tokens | 749.5500 | 755.3500 | +5.8000 | [-126.4500, 135.4000] | 20 |

### personalized / sparse

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 0.7000 | -0.3000 | [-0.5000, -0.1000] | 20 |
| reflections | 0.0000 | 0.3000 | +0.3000 | [0.1000, 0.5000] | 20 |
| llm_latency_seconds | 5.8290 | 26.0577 | +20.2287 | [9.9928, 33.6844] | 20 |
| completion_tokens | 139.1000 | 331.1500 | +192.0500 | [70.3500, 379.2500] | 20 |
| answer_fallback | 0.0000 | 0.1000 | +0.1000 | [0.0000, 0.2500] | 20 |
| inference_latency_seconds | 19.2585 | 34.7195 | +15.4609 | [2.4650, 33.1359] | 20 |
| inference_completion_tokens | 793.3500 | 1460.5500 | +667.2000 | [396.6500, 920.4000] | 20 |

### personalized / warm

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 0.6000 | -0.4000 | [-0.6000, -0.2000] | 20 |
| reflections | 0.0000 | 0.4000 | +0.4000 | [0.2000, 0.6000] | 20 |
| llm_latency_seconds | 6.4813 | 13.1593 | +6.6780 | [3.0247, 11.9476] | 20 |
| completion_tokens | 144.7500 | 231.1000 | +86.3500 | [45.1000, 130.2000] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_latency_seconds | 18.5819 | 16.7141 | -1.8678 | [-5.5265, 2.2354] | 20 |
| inference_completion_tokens | 800.1000 | 843.5000 | +43.4000 | [-60.2000, 158.2500] | 20 |

### similar / sparse

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 0.9500 | -0.0500 | [-0.1500, 0.0000] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 0.9500 | -0.0500 | [-0.1500, 0.0000] | 20 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| llm_latency_seconds | 6.8344 | 16.7186 | +9.8842 | [2.9747, 22.8511] | 20 |
| completion_tokens | 163.9000 | 641.1000 | +477.2000 | [358.4000, 584.0500] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 19 |
| inference_latency_seconds | 19.7861 | 21.4132 | +1.6271 | [-3.7948, 8.1318] | 20 |
| inference_completion_tokens | 813.4500 | 1018.9000 | +205.4500 | [-12.5000, 442.0000] | 20 |

### similar / warm

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| llm_latency_seconds | 6.6288 | 9.2101 | +2.5813 | [1.5686, 3.6915] | 20 |
| completion_tokens | 132.8000 | 430.2500 | +297.4500 | [175.4000, 414.3500] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_latency_seconds | 19.0071 | 15.3087 | -3.6983 | [-5.6522, -1.6173] | 20 |
| inference_completion_tokens | 801.1000 | 958.5500 | +157.4500 | [8.7000, 349.5000] | 20 |
