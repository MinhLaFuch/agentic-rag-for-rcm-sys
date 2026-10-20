# Ablation Comparison: planner_template_vs_llm

**Agent A:** planner (group: infer_template)
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
| llm_latency_seconds | 5.6252 | 5.8987 | +0.2735 | [-1.1275, 1.3880] | 6 |
| completion_tokens | 27.0000 | 56.8333 | +29.8333 | [18.0000, 43.6667] | 6 |
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
| llm_latency_seconds | 15.0577 | 6.7532 | -8.3046 | [-18.4140, -2.3993] | 20 |
| completion_tokens | 153.1500 | 161.8500 | +8.7000 | [-25.3000, 37.3000] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 17 |
| inference_latency_seconds | 0.0000 | 11.1328 | +11.1328 | [8.2555, 13.9624] | 20 |
| inference_completion_tokens | 0.0000 | 735.3500 | +735.3500 | [557.4500, 902.2500] | 20 |

### Kind: constrained
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.9750 | 0.8750 | -0.1000 | [-0.2250, 0.0000] | 40 |
| recall@10 | 0.1750 | 0.1750 | +0.0000 | [-0.0750, 0.0750] | 40 |
| ndcg@10 | 0.1077 | 0.0998 | -0.0079 | [-0.0467, 0.0217] | 40 |
| constraint_satisfaction | 0.9975 | 0.9450 | -0.0525 | [-0.1175, -0.0075] | 40 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| llm_latency_seconds | 10.9347 | 6.8157 | -4.1190 | [-6.3099, -2.6707] | 40 |
| completion_tokens | 178.8750 | 180.5000 | +1.6250 | [-11.1250, 12.9000] | 40 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 39 |
| inference_latency_seconds | 0.0000 | 11.0184 | +11.0184 | [9.7923, 12.3785] | 40 |
| inference_completion_tokens | 0.0000 | 690.3000 | +690.3000 | [626.4500, 753.3000] | 40 |

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
| llm_latency_seconds | 7.4305 | 49.1337 | +41.7032 | [26.7586, 57.9657] | 40 |
| completion_tokens | 97.3000 | 384.8000 | +287.5000 | [167.9500, 439.4250] | 40 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 1 |
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
| llm_latency_seconds | 6.5930 | 12.2785 | +5.6855 | [2.1547, 10.8276] | 40 |
| completion_tokens | 107.8250 | 572.1000 | +464.2750 | [370.0500, 555.0750] | 40 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| inference_latency_seconds | 0.0000 | 21.9173 | +21.9173 | [18.3782, 25.8938] | 40 |
| inference_completion_tokens | 0.0000 | 971.3750 | +971.3750 | [877.4750, 1080.6250] | 40 |

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
| llm_latency_seconds | 5.6252 | 5.8987 | +0.2735 | [-1.1275, 1.3880] | 6 |
| completion_tokens | 27.0000 | 56.8333 | +29.8333 | [18.0000, 43.6667] | 6 |
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
| llm_latency_seconds | 15.0577 | 6.7532 | -8.3046 | [-18.4140, -2.3993] | 20 |
| completion_tokens | 153.1500 | 161.8500 | +8.7000 | [-25.3000, 37.3000] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 17 |
| inference_latency_seconds | 0.0000 | 11.1328 | +11.1328 | [8.2555, 13.9624] | 20 |
| inference_completion_tokens | 0.0000 | 735.3500 | +735.3500 | [557.4500, 902.2500] | 20 |

### constrained / sparse
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.9500 | 0.8500 | -0.1000 | [-0.3000, 0.1000] | 20 |
| recall@10 | 0.2500 | 0.2500 | +0.0000 | [-0.1500, 0.1500] | 20 |
| ndcg@10 | 0.1759 | 0.1588 | -0.0171 | [-0.0946, 0.0434] | 20 |
| constraint_satisfaction | 0.9950 | 0.9550 | -0.0400 | [-0.1050, 0.0050] | 20 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| llm_latency_seconds | 11.4452 | 6.9752 | -4.4700 | [-8.5480, -1.9905] | 20 |
| completion_tokens | 179.9000 | 184.4000 | +4.5000 | [-7.5000, 15.7000] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_latency_seconds | 0.0000 | 11.0421 | +11.0421 | [9.6456, 12.8531] | 20 |
| inference_completion_tokens | 0.0000 | 712.4000 | +712.4000 | [649.7000, 782.9000] | 20 |

### constrained / warm
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 0.9000 | -0.1000 | [-0.2500, 0.0000] | 20 |
| recall@10 | 0.1000 | 0.1000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0395 | 0.0408 | +0.0013 | [0.0000, 0.0040] | 20 |
| constraint_satisfaction | 1.0000 | 0.9350 | -0.0650 | [-0.1800, 0.0000] | 20 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| llm_latency_seconds | 10.4242 | 6.6562 | -3.7680 | [-4.8882, -2.6682] | 20 |
| completion_tokens | 177.8500 | 176.6000 | -1.2500 | [-23.4500, 18.6000] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 19 |
| inference_latency_seconds | 0.0000 | 10.9946 | +10.9946 | [9.0469, 13.0658] | 20 |
| inference_completion_tokens | 0.0000 | 668.2000 | +668.2000 | [559.0500, 769.9500] | 20 |

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
| llm_latency_seconds | 7.2140 | 80.8775 | +73.6635 | [52.0112, 96.9251] | 20 |
| completion_tokens | 90.8500 | 541.9500 | +451.1000 | [229.4000, 718.3500] | 20 |
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
| llm_latency_seconds | 7.6469 | 17.3899 | +9.7430 | [2.2296, 18.8280] | 20 |
| completion_tokens | 103.7500 | 227.6500 | +123.9000 | [63.0000, 194.1500] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 1 |
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
| llm_latency_seconds | 6.0360 | 10.2774 | +4.2414 | [3.3905, 5.0165] | 20 |
| completion_tokens | 107.4500 | 685.9500 | +578.5000 | [478.0000, 663.1000] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_latency_seconds | 0.0000 | 23.2251 | +23.2251 | [17.5900, 29.8204] | 20 |
| inference_completion_tokens | 0.0000 | 1022.4000 | +1022.4000 | [871.0000, 1199.5500] | 20 |

### similar / warm

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| llm_latency_seconds | 7.1500 | 14.2796 | +7.1296 | [0.1139, 17.4202] | 20 |
| completion_tokens | 108.2000 | 458.2500 | +350.0500 | [207.1500, 496.7500] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_latency_seconds | 0.0000 | 20.6094 | +20.6094 | [16.5180, 25.1711] | 20 |
| inference_completion_tokens | 0.0000 | 920.3500 | +920.3500 | [822.7000, 1053.6500] | 20 |
