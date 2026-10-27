# Ablation Comparison: planner_memory_reflect0_vs_reflect1

**Agent A:** planner_memory (group: reflect_0)
**Agent B:** planner_memory (group: reflect_1)
**Bootstrap resamples:** 10000
**Confidence level:** 95.0%
**k:** 10

**Number of paired requests:** 66

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
| llm_latency_seconds | 3.0493 | 3.4503 | +0.4010 | [0.2448, 0.5653] | 6 |
| completion_tokens | 87.1667 | 85.6667 | -1.5000 | [-22.1667, 21.8333] | 6 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |

### Kind: personalized

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.4000 | 0.9333 | +0.5333 | [0.3333, 0.7333] | 30 |
|  | McNemar: b=1.0, c=17.0, p=0.001 | | | | |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 30 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 30 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.4000 | 0.5000 | +0.1000 | [-0.1667, 0.3333] | 30 |
|  | McNemar: b=6.0, c=9.0, p=1.000 | | | | |
| reflections | 0.0000 | 0.5000 | +0.5000 | [0.3333, 0.6667] | 30 |
| llm_latency_seconds | 5.5020 | 8.3067 | +2.8047 | [1.6412, 4.0177] | 30 |
| completion_tokens | 324.7667 | 491.5333 | +166.7667 | [94.6000, 241.9667] | 30 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| inference_latency_seconds | 6.7949 | 7.4980 | +0.7031 | [-4.9450, 4.4265] | 30 |
| inference_completion_tokens | 428.9000 | 743.9333 | +315.0333 | [156.3000, 474.3000] | 30 |

### Kind: similar

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 30 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 30 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 30 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 30 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 30 |
| llm_latency_seconds | 4.5218 | 5.2203 | +0.6985 | [-1.0385, 3.5433] | 30 |
| completion_tokens | 168.2000 | 168.0000 | -0.2000 | [-8.8000, 8.4667] | 30 |
| answer_fallback | 0.0333 | 0.0333 | +0.0000 | [-0.1000, 0.1000] | 30 |
| inference_latency_seconds | 12.3651 | 12.6802 | +0.3151 | [-1.6677, 2.1728] | 30 |
| inference_completion_tokens | 1210.9333 | 1159.5000 | -51.4333 | [-274.3000, 168.6000] | 30 |

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
| llm_latency_seconds | 3.0493 | 3.4503 | +0.4010 | [0.2448, 0.5653] | 6 |
| completion_tokens | 87.1667 | 85.6667 | -1.5000 | [-22.1667, 21.8333] | 6 |
| answer_fallback | — | — | — | — | 0 |
| inference_latency_seconds | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |
| inference_completion_tokens | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 6 |

### personalized / sparse

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.3333 | 0.9333 | +0.6000 | [0.2667, 0.8667] | 15 |
|  | McNemar: b=1.0, c=10.0, p=0.050 | | | | |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.3333 | 0.4000 | +0.0667 | [-0.2667, 0.4000] | 15 |
| reflections | 0.0000 | 0.6000 | +0.6000 | [0.3333, 0.8667] | 15 |
| llm_latency_seconds | 5.3895 | 8.8051 | +3.4156 | [1.4032, 5.5257] | 15 |
| completion_tokens | 311.0000 | 531.3333 | +220.3333 | [100.8000, 337.8667] | 15 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 8 |
| inference_latency_seconds | 4.4031 | 7.8281 | +3.4249 | [1.2216, 5.6575] | 15 |
| inference_completion_tokens | 412.0667 | 796.5333 | +384.4667 | [172.6000, 599.6667] | 15 |

### personalized / warm

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 0.4667 | 0.9333 | +0.4667 | [0.2000, 0.7333] | 15 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 0.4667 | 0.6000 | +0.1333 | [-0.2000, 0.4667] | 15 |
| reflections | 0.0000 | 0.4000 | +0.4000 | [0.1333, 0.6667] | 15 |
| llm_latency_seconds | 5.6145 | 7.8084 | +2.1939 | [1.0051, 3.5020] | 15 |
| completion_tokens | 338.5333 | 451.7333 | +113.2000 | [34.2667, 198.6000] | 15 |
| answer_fallback | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 7 |
| inference_latency_seconds | 9.1866 | 7.1679 | -2.0187 | [-12.9824, 4.6897] | 15 |
| inference_completion_tokens | 445.7333 | 691.3333 | +245.6000 | [14.1333, 464.9333] | 15 |

### similar / sparse

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| llm_latency_seconds | 3.7572 | 4.0897 | +0.3325 | [-0.0581, 0.7713] | 15 |
| completion_tokens | 161.9333 | 162.3333 | +0.4000 | [-9.9333, 12.1333] | 15 |
| answer_fallback | 0.0000 | 0.0667 | +0.0667 | [0.0000, 0.2000] | 15 |
| inference_latency_seconds | 11.4729 | 13.4989 | +2.0261 | [-0.1385, 4.1929] | 15 |
| inference_completion_tokens | 1171.1333 | 1168.0667 | -3.0667 | [-317.4667, 308.1333] | 15 |

### similar / warm

| Metric | Mean A | Mean B | Diff (B-A) | 95% CI | n |
|--------|--------|--------|-----------|--------|---|
| task_success | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| recall@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| ndcg@10 | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| constraint_satisfaction | — | — | — | — | 0 |
| first_attempt_ok | 1.0000 | 1.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| reflections | 0.0000 | 0.0000 | +0.0000 | [0.0000, 0.0000] | 15 |
| llm_latency_seconds | 5.2864 | 6.3509 | +1.0645 | [-2.2825, 6.6845] | 15 |
| completion_tokens | 174.4667 | 173.6667 | -0.8000 | [-14.5333, 11.8667] | 15 |
| answer_fallback | 0.0667 | 0.0000 | -0.0667 | [-0.2000, 0.0000] | 15 |
| inference_latency_seconds | 13.2573 | 11.8615 | -1.3959 | [-4.4181, 1.4511] | 15 |
| inference_completion_tokens | 1250.7333 | 1150.9333 | -99.8000 | [-428.0000, 216.5333] | 15 |
