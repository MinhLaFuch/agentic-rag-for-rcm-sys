# Ablation Comparison: reflect_effect_planner

**Agent A:** planner (group: exp_5_agents_planner_inference_mode_template_reflect_rounds_0_multi_turn_True)
**Agent B:** planner (group: exp_6_agents_planner_inference_mode_template_reflect_rounds_1_multi_turn_True)
**Bootstrap resamples:** 10000
**Confidence level:** 95.0%
**k:** 10

**Number of paired requests:** 152

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
| llm_latency_seconds | 3.2628 | 2.2682 | -0.9947 | [-2.9295, 0.0210] | 6 |
| completion_tokens | 43.3333 | 37.3333 | -6.0000 | [-24.3333, 12.3333] | 6 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |

### Kind: cold_text
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.5000 | 0.3000 | -0.2000 | [-0.4500, 0.0500] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | 0.5700 | 0.5300 | -0.0400 | [-0.2650, 0.1850] | 20 |
| first_attempt_ok | 0.6500 | 0.6500 | +0.0000 | [-0.2500, 0.2500] | 20 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| llm_latency_seconds | 7.3773 | 6.7859 | -0.5913 | [-2.6007, 1.0664] | 20 |
| completion_tokens | 140.2500 | 142.0000 | +1.7500 | [-20.8500, 26.2000] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 9 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |

### Kind: exclusion
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.2000 | 0.2500 | +0.0500 | [-0.1500, 0.2500] | 40 |
|  | McNemar: b=7.0, c=9.0, p=1.000 | | | | |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 16 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 16 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.7750 | 0.6000 | -0.1750 | [-0.4000, 0.0500] | 40 |
|  | McNemar: b=15.0, c=8.0, p=1.000 | | | | |
| reflections | 0.0000 | 0.1500 | +0.1500 | [0.0500, 0.2750] | 40 |
| llm_latency_seconds | 12.4526 | 12.9399 | +0.4872 | [-1.1031, 2.1558] | 40 |
| completion_tokens | 389.8750 | 438.7500 | +48.8750 | [-10.7000, 110.5000] | 40 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 3 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |

### Kind: personalized

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | — | — | — | — | 0 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| llm_latency_seconds | 9.0622 | 7.2133 | -1.8489 | [-3.2281, -0.3757] | 40 |
| completion_tokens | 178.9500 | 140.3750 | -38.5750 | [-70.9250, -7.0250] | 40 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |

### Kind: similar

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.9500 | 0.9500 | +0.0000 | [0.0000, 0.0000] | 40 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.9500 | 0.9500 | +0.0000 | [0.0000, 0.0000] | 40 |
| reflections | 0.0000 | 0.0500 | +0.0500 | [0.0000, 0.1250] | 40 |
| llm_latency_seconds | 7.3766 | 7.1644 | -0.2122 | [-1.1400, 0.7657] | 40 |
| completion_tokens | 166.7750 | 165.0750 | -1.7000 | [-29.5750, 30.0250] | 40 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 38 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 40 |

### Kind: unanswerable

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.3333 | 1.0000 | +0.6667 | [0.3333, 1.0000] | 6 |
| recall@10 | — | — | — | — | 0 |
| ndcg@10 | — | — | — | — | 0 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.3333 | 0.1667 | -0.1667 | [-0.6667, 0.3333] | 6 |
| reflections | 0.0000 | 0.8333 | +0.8333 | [0.5000, 1.0000] | 6 |
| llm_latency_seconds | 5.5000 | 11.6460 | +6.1460 | [2.5415, 9.7738] | 6 |
| completion_tokens | 106.6667 | 266.6667 | +160.0000 | [32.1667, 287.6667] | 6 |
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
| llm_latency_seconds | 3.2628 | 2.2682 | -0.9947 | [-2.9295, 0.0210] | 6 |
| completion_tokens | 43.3333 | 37.3333 | -6.0000 | [-24.3333, 12.3333] | 6 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |

### cold_text / cold
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.5000 | 0.3000 | -0.2000 | [-0.4500, 0.0500] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | 0.5700 | 0.5300 | -0.0400 | [-0.2650, 0.1850] | 20 |
| first_attempt_ok | 0.6500 | 0.6500 | +0.0000 | [-0.2500, 0.2500] | 20 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| llm_latency_seconds | 7.3773 | 6.7859 | -0.5913 | [-2.6007, 1.0664] | 20 |
| completion_tokens | 140.2500 | 142.0000 | +1.7500 | [-20.8500, 26.2000] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 9 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |

### exclusion / sparse
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.2000 | 0.2500 | +0.0500 | [-0.2500, 0.3500] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 4 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 4 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.6500 | 0.6500 | +0.0000 | [-0.3500, 0.3500] | 20 |
|  | McNemar: b=7.0, c=7.0, p=1.000 | | | | |
| reflections | 0.0000 | 0.1500 | +0.1500 | [0.0000, 0.3000] | 20 |
| llm_latency_seconds | 13.2858 | 12.5306 | -0.7553 | [-2.7663, 1.5294] | 20 |
| completion_tokens | 419.2500 | 413.6500 | -5.6000 | [-77.7500, 70.7500] | 20 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |

### exclusion / warm
⚠️ **ORACLE** (constraints from held-out items - upper bound, not real query)

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.2000 | 0.2500 | +0.0500 | [-0.2000, 0.3000] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 12 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 12 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.9000 | 0.5500 | -0.3500 | [-0.6000, -0.1000] | 20 |
| reflections | 0.0000 | 0.1500 | +0.1500 | [0.0000, 0.3000] | 20 |
| llm_latency_seconds | 11.6194 | 13.3492 | +1.7297 | [-0.6085, 4.0228] | 20 |
| completion_tokens | 360.5000 | 463.8500 | +103.3500 | [12.6000, 189.3500] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 3 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |

### personalized / sparse

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | — | — | — | — | 0 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| llm_latency_seconds | 8.6070 | 7.1609 | -1.4461 | [-2.9490, 0.0303] | 20 |
| completion_tokens | 187.4500 | 140.2500 | -47.2000 | [-89.2500, -7.8000] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 11 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |

### personalized / warm

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | — | — | — | — | 0 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| llm_latency_seconds | 9.5173 | 7.2657 | -2.2516 | [-4.5767, 0.3132] | 20 |
| completion_tokens | 170.4500 | 140.5000 | -29.9500 | [-77.3500, 19.0500] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 9 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |

### similar / sparse

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.9500 | 0.9500 | +0.0000 | [0.0000, 0.0000] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.9500 | 0.9500 | +0.0000 | [0.0000, 0.0000] | 20 |
| reflections | 0.0000 | 0.0500 | +0.0500 | [0.0000, 0.1500] | 20 |
| llm_latency_seconds | 6.8829 | 7.3001 | +0.4172 | [-0.8182, 1.8104] | 20 |
| completion_tokens | 180.7500 | 180.3000 | -0.4500 | [-50.6500, 53.1500] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 19 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |

### similar / warm

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.9500 | 0.9500 | +0.0000 | [0.0000, 0.0000] | 20 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.9500 | 0.9500 | +0.0000 | [0.0000, 0.0000] | 20 |
| reflections | 0.0000 | 0.0500 | +0.0500 | [0.0000, 0.1500] | 20 |
| llm_latency_seconds | 7.8703 | 7.0288 | -0.8415 | [-2.1362, 0.5516] | 20 |
| completion_tokens | 152.8000 | 149.8500 | -2.9500 | [-29.2500, 29.4500] | 20 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 19 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 20 |

### unanswerable / none

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.3333 | 1.0000 | +0.6667 | [0.3333, 1.0000] | 6 |
| recall@10 | — | — | — | — | 0 |
| ndcg@10 | — | — | — | — | 0 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.3333 | 0.1667 | -0.1667 | [-0.6667, 0.3333] | 6 |
| reflections | 0.0000 | 0.8333 | +0.8333 | [0.5000, 1.0000] | 6 |
| llm_latency_seconds | 5.5000 | 11.6460 | +6.1460 | [2.5415, 9.7738] | 6 |
| completion_tokens | 106.6667 | 266.6667 | +160.0000 | [32.1667, 287.6667] | 6 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
