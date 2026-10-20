# Ablation Comparison: planner_reflect0_vs_reflect1

**Agent A:** planner (group: reflect_0)
**Agent B:** planner (group: reflect_1)
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
| llm_latency_seconds | 5.5418 | 5.8987 | +0.3568 | [-1.0417, 1.8098] | 6 |
| completion_tokens | 31.3333 | 56.8333 | +25.5000 | [12.6667, 39.3333] | 6 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |

### Kind: cold_text
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 0.8500 | -0.1500 | [-0.3000, 0.0000] | 20 |
| recall@10 | 0.0667 | 0.0417 | -0.0250 | [-0.1500, 0.0750] | 20 |
| ndcg@10 | 0.0735 | 0.0384 | -0.0351 | [-0.1500, 0.0447] | 20 |
| constraint_satisfaction | 1.0000 | 0.8500 | -0.1500 | [-0.3000, 0.0000] | 20 |
| first_attempt_ok | 1.0000 | 0.8500 | -0.1500 | [-0.3000, 0.0000] | 20 |
| reflections | 0.0000 | 0.0500 | +0.0500 | [0.0000, 0.1500] | 20 |
| llm_latency_seconds | 8.0702 | 6.7532 | -1.3170 | [-2.6661, -0.1811] | 20 |
| completion_tokens | 155.6500 | 161.8500 | +6.2000 | [-27.7500, 35.1500] | 20 |
| answer_fallback | 0.0588 | 0.0000 | -0.0588 | [-0.1765, 0.0000] | 17 |
| inference_latency_seconds | 17.7999 | 11.1328 | -6.6671 | [-10.1811, -3.1942] | 20 |
| inference_completion_tokens | 716.4500 | 735.3500 | +18.9000 | [-165.1500, 194.6000] | 20 |

### Kind: constrained
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 0.8750 | -0.1250 | [-0.2250, -0.0250] | 40 |
| recall@10 | 0.2000 | 0.1750 | -0.0250 | [-0.1000, 0.0500] | 40 |
| ndcg@10 | 0.1152 | 0.0998 | -0.0154 | [-0.0545, 0.0148] | 40 |
| constraint_satisfaction | 1.0000 | 0.9450 | -0.0550 | [-0.1200, -0.0100] | 40 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| llm_latency_seconds | 9.8722 | 6.8157 | -3.0565 | [-4.0406, -2.2030] | 40 |
| completion_tokens | 189.0000 | 180.5000 | -8.5000 | [-24.1250, 4.5750] | 40 |
| answer_fallback | 0.0513 | 0.0000 | -0.0513 | [-0.1282, 0.0000] | 39 |
| inference_latency_seconds | 19.5499 | 11.0184 | -8.5315 | [-10.6163, -6.5650] | 40 |
| inference_completion_tokens | 771.8750 | 690.3000 | -81.5750 | [-165.8000, -2.3250] | 40 |

### Kind: personalized

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | — | — | — | — | 0 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 0.5250 | -0.4750 | [-0.6250, -0.3250] | 40 |
|  | McNemar: b=19.0, c=0.0, p=0.001 | | | | |
| reflections | 0.0000 | 0.4750 | +0.4750 | [0.3250, 0.6250] | 40 |
| llm_latency_seconds | 7.1497 | 49.1337 | +41.9840 | [27.3685, 58.0086] | 40 |
| completion_tokens | 89.4750 | 384.8000 | +295.3250 | [179.8000, 446.1000] | 40 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 13.1032 | +13.1032 | [8.3490, 18.5924] | 40 |
| inference_completion_tokens | 0.0000 | 571.9500 | +571.9500 | [417.6750, 737.0500] | 40 |

### Kind: similar

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| llm_latency_seconds | 6.1777 | 12.2785 | +6.1007 | [3.0516, 11.0125] | 40 |
| completion_tokens | 110.1250 | 572.1000 | +461.9750 | [368.8500, 552.5000] | 40 |
| answer_fallback | 0.0250 | 0.0000 | -0.0250 | [-0.0750, 0.0000] | 40 |
| inference_latency_seconds | 19.5445 | 21.9173 | +2.3727 | [-1.5399, 6.6396] | 40 |
| inference_completion_tokens | 806.8750 | 971.3750 | +164.5000 | [54.0250, 285.1750] | 40 |

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
| llm_latency_seconds | 5.5418 | 5.8987 | +0.3568 | [-1.0417, 1.8098] | 6 |
| completion_tokens | 31.3333 | 56.8333 | +25.5000 | [12.6667, 39.3333] | 6 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |

### cold_text / cold
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 0.8500 | -0.1500 | [-0.3000, 0.0000] | 20 |
| recall@10 | 0.0667 | 0.0417 | -0.0250 | [-0.1500, 0.0750] | 20 |
| ndcg@10 | 0.0735 | 0.0384 | -0.0351 | [-0.1500, 0.0447] | 20 |
| constraint_satisfaction | 1.0000 | 0.8500 | -0.1500 | [-0.3000, 0.0000] | 20 |
| first_attempt_ok | 1.0000 | 0.8500 | -0.1500 | [-0.3000, 0.0000] | 20 |
| reflections | 0.0000 | 0.0500 | +0.0500 | [0.0000, 0.1500] | 20 |
| llm_latency_seconds | 8.0702 | 6.7532 | -1.3170 | [-2.6661, -0.1811] | 20 |
| completion_tokens | 155.6500 | 161.8500 | +6.2000 | [-27.7500, 35.1500] | 20 |
| answer_fallback | 0.0588 | 0.0000 | -0.0588 | [-0.1765, 0.0000] | 17 |
| inference_latency_seconds | 17.7999 | 11.1328 | -6.6671 | [-10.1811, -3.1942] | 20 |
| inference_completion_tokens | 716.4500 | 735.3500 | +18.9000 | [-165.1500, 194.6000] | 20 |

### constrained / sparse
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 0.8500 | -0.1500 | [-0.3000, 0.0000] | 20 |
| recall@10 | 0.3000 | 0.2500 | -0.0500 | [-0.2000, 0.1000] | 20 |
| ndcg@10 | 0.1903 | 0.1588 | -0.0315 | [-0.1091, 0.0289] | 20 |
| constraint_satisfaction | 1.0000 | 0.9550 | -0.0450 | [-0.1050, 0.0000] | 20 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| llm_latency_seconds | 9.7508 | 6.9752 | -2.7756 | [-4.4781, -1.4842] | 20 |
| completion_tokens | 190.2500 | 184.4000 | -5.8500 | [-26.7500, 11.9500] | 20 |
| answer_fallback | 0.0500 | 0.0000 | -0.0500 | [-0.1500, 0.0000] | 20 |
| inference_latency_seconds | 18.5295 | 11.0421 | -7.4874 | [-10.3334, -4.8753] | 20 |
| inference_completion_tokens | 780.1500 | 712.4000 | -67.7500 | [-176.6000, 27.7000] | 20 |

### constrained / warm
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 0.9000 | -0.1000 | [-0.2500, 0.0000] | 20 |
| recall@10 | 0.1000 | 0.1000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0401 | 0.0408 | +0.0007 | [0.0000, 0.0022] | 20 |
| constraint_satisfaction | 1.0000 | 0.9350 | -0.0650 | [-0.1800, 0.0000] | 20 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| llm_latency_seconds | 9.9937 | 6.6562 | -3.3375 | [-4.3908, -2.3403] | 20 |
| completion_tokens | 187.7500 | 176.6000 | -11.1500 | [-35.3000, 6.7500] | 20 |
| answer_fallback | 0.0526 | 0.0000 | -0.0526 | [-0.1579, 0.0000] | 19 |
| inference_latency_seconds | 20.5702 | 10.9946 | -9.5756 | [-12.5303, -6.7498] | 20 |
| inference_completion_tokens | 763.6000 | 668.2000 | -95.4000 | [-222.0500, 27.5500] | 20 |

### personalized / sparse

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | — | — | — | — | 0 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 0.1000 | -0.9000 | [-1.0000, -0.7500] | 20 |
|  | McNemar: b=18.0, c=0.0, p=0.001 | | | | |
| reflections | 0.0000 | 0.9000 | +0.9000 | [0.7500, 1.0000] | 20 |
| llm_latency_seconds | 7.6156 | 80.8775 | +73.2619 | [51.7431, 96.4472] | 20 |
| completion_tokens | 89.4000 | 541.9500 | +452.5500 | [230.9500, 720.5000] | 20 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 13.6164 | +13.6164 | [5.8641, 23.6235] | 20 |
| inference_completion_tokens | 0.0000 | 553.7500 | +553.7500 | [287.0000, 849.4500] | 20 |

### personalized / warm

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | — | — | — | — | 0 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 0.9500 | -0.0500 | [-0.1500, 0.0000] | 20 |
| reflections | 0.0000 | 0.0500 | +0.0500 | [0.0000, 0.1500] | 20 |
| llm_latency_seconds | 6.6837 | 17.3899 | +10.7061 | [3.5858, 19.3524] | 20 |
| completion_tokens | 89.5500 | 227.6500 | +138.1000 | [98.4500, 195.6000] | 20 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 12.5899 | +12.5899 | [7.9790, 17.8376] | 20 |
| inference_completion_tokens | 0.0000 | 590.1500 | +590.1500 | [434.5000, 743.4000] | 20 |

### similar / sparse

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| llm_latency_seconds | 6.3069 | 10.2774 | +3.9704 | [2.6963, 5.0432] | 20 |
| completion_tokens | 112.6000 | 685.9500 | +573.3500 | [473.0000, 658.3000] | 20 |
| answer_fallback | 0.0500 | 0.0000 | -0.0500 | [-0.1500, 0.0000] | 20 |
| inference_latency_seconds | 19.5219 | 23.2251 | +3.7032 | [-2.7368, 10.9180] | 20 |
| inference_completion_tokens | 809.7000 | 1022.4000 | +212.7000 | [27.9500, 413.1500] | 20 |

### similar / warm

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| llm_latency_seconds | 6.0485 | 14.2796 | +8.2311 | [2.4568, 17.9147] | 20 |
| completion_tokens | 107.6500 | 458.2500 | +350.6000 | [207.3500, 497.7500] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_latency_seconds | 19.5671 | 20.6094 | +1.0423 | [-3.3966, 6.0103] | 20 |
| inference_completion_tokens | 804.0500 | 920.3500 | +116.3000 | [12.2500, 256.2500] | 20 |
