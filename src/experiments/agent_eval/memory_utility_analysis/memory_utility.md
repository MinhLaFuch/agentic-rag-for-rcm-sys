# Memory utility (paired, multi-run)

- baseline agent: `planner`, memory agent: `planner_memory`
- runs: baseline=3, memory=3; seed=42; bootstrap=5000 x 0.95; min_n=20

REALISTIC and ORACLE groups are reported separately and must not be averaged together.
Verdicts are per group; `inconclusive` is the default.

## task_success

| group | n_pairs | unscored (base/mem) | baseline | memory | diff [CI] | run-std (b/m) | W/L/T | verdict |
|---|---|---|---|---|---|---|---|---|
| oracle | 6 | 0/0 | 0.417 | 0.167 | -0.250 [-0.583, +0.000] | 0.118/0.000 | 0/2/4 | inconclusive |
| oracle/cold_text | 2 | 0/0 | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/2 | inconclusive |
| oracle/cold_text/cold | 2 | 0/0 | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/2 | inconclusive |
| oracle/constrained | 4 | 0/0 | 0.625 | 0.250 | -0.375 [-0.750, +0.000] | 0.177/0.000 | 0/2/2 | inconclusive |
| oracle/constrained/sparse | 2 | 0/0 | 0.750 | 0.000 | -0.750 [-1.000, -0.500] | 0.354/0.000 | 0/2/0 | inconclusive |
| oracle/constrained/warm | 2 | 0/0 | 0.500 | 0.500 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/2 | inconclusive |
| realistic | 14 | 0/0 | 0.857 | 0.929 | +0.071 [+0.000, +0.214] | 0.101/0.101 | 1/0/13 | inconclusive |
| realistic/ambiguous | 6 | 0/0 | 1.000 | 1.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/6 | inconclusive |
| realistic/ambiguous/none | 6 | 0/0 | 1.000 | 1.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/6 | inconclusive |
| realistic/personalized | 4 | 0/0 | 0.500 | 0.750 | +0.250 [+0.000, +0.750] | 0.354/0.354 | 1/0/3 | inconclusive |
| realistic/personalized/sparse | 2 | 0/0 | 0.750 | 0.750 | +0.000 [+0.000, +0.000] | 0.354/0.354 | 0/0/2 | inconclusive |
| realistic/personalized/warm | 2 | 0/0 | 0.250 | 0.750 | +0.500 [+0.000, +1.000] | 0.354/0.354 | 1/0/1 | inconclusive |
| realistic/similar | 4 | 0/0 | 1.000 | 1.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/4 | inconclusive |
| realistic/similar/sparse | 2 | 0/0 | 1.000 | 1.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/2 | inconclusive |
| realistic/similar/warm | 2 | 0/0 | 1.000 | 1.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/2 | inconclusive |

> ORACLE requests (built from held-out targets): upper bound, not a real query log
> n=14 < 20: too few pairs for a reliable estimate
> n=2 < 20: too few pairs for a reliable estimate
> n=4 < 20: too few pairs for a reliable estimate
> n=6 < 20: too few pairs for a reliable estimate

## recall@10

| group | n_pairs | unscored (base/mem) | baseline | memory | diff [CI] | run-std (b/m) | W/L/T | verdict |
|---|---|---|---|---|---|---|---|---|
| oracle | 6 | 0/0 | 0.167 | 0.000 | -0.167 [-0.500, +0.000] | 0.000/0.000 | 0/1/5 | inconclusive |
| oracle/cold_text | 2 | 0/0 | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/2 | inconclusive |
| oracle/cold_text/cold | 2 | 0/0 | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/2 | inconclusive |
| oracle/constrained | 4 | 0/0 | 0.250 | 0.000 | -0.250 [-0.750, +0.000] | 0.000/0.000 | 0/1/3 | inconclusive |
| oracle/constrained/sparse | 2 | 0/0 | 0.500 | 0.000 | -0.500 [-1.000, +0.000] | 0.000/0.000 | 0/1/1 | inconclusive |
| oracle/constrained/warm | 2 | 0/0 | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/2 | inconclusive |
| realistic | 8 | 6/6 | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/8 | inconclusive |
| realistic/ambiguous | 0 | 6/6 | - | - | - | - | - | no_pairs |
| realistic/ambiguous/none | 0 | 6/6 | - | - | - | - | - | no_pairs |
| realistic/personalized | 4 | 0/0 | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/4 | inconclusive |
| realistic/personalized/sparse | 2 | 0/0 | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/2 | inconclusive |
| realistic/personalized/warm | 2 | 0/0 | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/2 | inconclusive |
| realistic/similar | 4 | 0/0 | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/4 | inconclusive |
| realistic/similar/sparse | 2 | 0/0 | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/2 | inconclusive |
| realistic/similar/warm | 2 | 0/0 | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/2 | inconclusive |

> 6 request(s) unscored for baseline, 6 for memory (e.g. personalized is not scored for a planner without MemoryTool): excluded from the pair
> ORACLE requests (built from held-out targets): upper bound, not a real query log
> n=2 < 20: too few pairs for a reliable estimate
> n=4 < 20: too few pairs for a reliable estimate
> n=6 < 20: too few pairs for a reliable estimate
> n=8 < 20: too few pairs for a reliable estimate

## ndcg@10

| group | n_pairs | unscored (base/mem) | baseline | memory | diff [CI] | run-std (b/m) | W/L/T | verdict |
|---|---|---|---|---|---|---|---|---|
| oracle | 6 | 0/0 | 0.105 | 0.000 | -0.105 [-0.315, +0.000] | 0.000/0.000 | 0/1/5 | inconclusive |
| oracle/cold_text | 2 | 0/0 | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/2 | inconclusive |
| oracle/cold_text/cold | 2 | 0/0 | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/2 | inconclusive |
| oracle/constrained | 4 | 0/0 | 0.158 | 0.000 | -0.158 [-0.473, +0.000] | 0.000/0.000 | 0/1/3 | inconclusive |
| oracle/constrained/sparse | 2 | 0/0 | 0.315 | 0.000 | -0.315 [-0.631, +0.000] | 0.000/0.000 | 0/1/1 | inconclusive |
| oracle/constrained/warm | 2 | 0/0 | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/2 | inconclusive |
| realistic | 8 | 6/6 | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/8 | inconclusive |
| realistic/ambiguous | 0 | 6/6 | - | - | - | - | - | no_pairs |
| realistic/ambiguous/none | 0 | 6/6 | - | - | - | - | - | no_pairs |
| realistic/personalized | 4 | 0/0 | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/4 | inconclusive |
| realistic/personalized/sparse | 2 | 0/0 | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/2 | inconclusive |
| realistic/personalized/warm | 2 | 0/0 | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/2 | inconclusive |
| realistic/similar | 4 | 0/0 | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/4 | inconclusive |
| realistic/similar/sparse | 2 | 0/0 | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/2 | inconclusive |
| realistic/similar/warm | 2 | 0/0 | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/2 | inconclusive |

> 6 request(s) unscored for baseline, 6 for memory (e.g. personalized is not scored for a planner without MemoryTool): excluded from the pair
> ORACLE requests (built from held-out targets): upper bound, not a real query log
> n=2 < 20: too few pairs for a reliable estimate
> n=4 < 20: too few pairs for a reliable estimate
> n=6 < 20: too few pairs for a reliable estimate
> n=8 < 20: too few pairs for a reliable estimate

## constraint_satisfaction

| group | n_pairs | unscored (base/mem) | baseline | memory | diff [CI] | run-std (b/m) | W/L/T | verdict |
|---|---|---|---|---|---|---|---|---|
| oracle | 6 | 0/0 | 0.417 | 0.242 | -0.175 [-0.458, +0.067] | 0.118/0.106 | 1/2/3 | inconclusive |
| oracle/cold_text | 2 | 0/0 | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/2 | inconclusive |
| oracle/cold_text/cold | 2 | 0/0 | 0.000 | 0.000 | +0.000 [+0.000, +0.000] | 0.000/0.000 | 0/0/2 | inconclusive |
| oracle/constrained | 4 | 0/0 | 0.625 | 0.362 | -0.263 [-0.625, +0.100] | 0.177/0.159 | 1/2/1 | inconclusive |
| oracle/constrained/sparse | 2 | 0/0 | 0.750 | 0.125 | -0.625 [-0.750, -0.500] | 0.354/0.177 | 0/2/0 | inconclusive |
| oracle/constrained/warm | 2 | 0/0 | 0.500 | 0.600 | +0.100 [+0.000, +0.200] | 0.000/0.141 | 1/0/1 | inconclusive |
| realistic | 0 | 14/14 | - | - | - | - | - | no_pairs |
| realistic/ambiguous | 0 | 6/6 | - | - | - | - | - | no_pairs |
| realistic/ambiguous/none | 0 | 6/6 | - | - | - | - | - | no_pairs |
| realistic/personalized | 0 | 4/4 | - | - | - | - | - | no_pairs |
| realistic/personalized/sparse | 0 | 2/2 | - | - | - | - | - | no_pairs |
| realistic/personalized/warm | 0 | 2/2 | - | - | - | - | - | no_pairs |
| realistic/similar | 0 | 4/4 | - | - | - | - | - | no_pairs |
| realistic/similar/sparse | 0 | 2/2 | - | - | - | - | - | no_pairs |
| realistic/similar/warm | 0 | 2/2 | - | - | - | - | - | no_pairs |

> 14 request(s) unscored for baseline, 14 for memory (e.g. personalized is not scored for a planner without MemoryTool): excluded from the pair
> 2 request(s) unscored for baseline, 2 for memory (e.g. personalized is not scored for a planner without MemoryTool): excluded from the pair
> 4 request(s) unscored for baseline, 4 for memory (e.g. personalized is not scored for a planner without MemoryTool): excluded from the pair
> 6 request(s) unscored for baseline, 6 for memory (e.g. personalized is not scored for a planner without MemoryTool): excluded from the pair
> ORACLE requests (built from held-out targets): upper bound, not a real query log
> n=2 < 20: too few pairs for a reliable estimate
> n=4 < 20: too few pairs for a reliable estimate
> n=6 < 20: too few pairs for a reliable estimate

## first_attempt_ok

| group | n_pairs | unscored (base/mem) | baseline | memory | diff [CI] | run-std (b/m) | W/L/T | verdict |
|---|---|---|---|---|---|---|---|---|
| oracle | 0 | 6/6 | - | - | - | - | - | no_pairs |
| oracle/cold_text | 0 | 2/2 | - | - | - | - | - | no_pairs |
| oracle/cold_text/cold | 0 | 2/2 | - | - | - | - | - | no_pairs |
| oracle/constrained | 0 | 4/4 | - | - | - | - | - | no_pairs |
| oracle/constrained/sparse | 0 | 2/2 | - | - | - | - | - | no_pairs |
| oracle/constrained/warm | 0 | 2/2 | - | - | - | - | - | no_pairs |
| realistic | 0 | 14/14 | - | - | - | - | - | no_pairs |
| realistic/ambiguous | 0 | 6/6 | - | - | - | - | - | no_pairs |
| realistic/ambiguous/none | 0 | 6/6 | - | - | - | - | - | no_pairs |
| realistic/personalized | 0 | 4/4 | - | - | - | - | - | no_pairs |
| realistic/personalized/sparse | 0 | 2/2 | - | - | - | - | - | no_pairs |
| realistic/personalized/warm | 0 | 2/2 | - | - | - | - | - | no_pairs |
| realistic/similar | 0 | 4/4 | - | - | - | - | - | no_pairs |
| realistic/similar/sparse | 0 | 2/2 | - | - | - | - | - | no_pairs |
| realistic/similar/warm | 0 | 2/2 | - | - | - | - | - | no_pairs |

> 14 request(s) unscored for baseline, 14 for memory (e.g. personalized is not scored for a planner without MemoryTool): excluded from the pair
> 2 request(s) unscored for baseline, 2 for memory (e.g. personalized is not scored for a planner without MemoryTool): excluded from the pair
> 4 request(s) unscored for baseline, 4 for memory (e.g. personalized is not scored for a planner without MemoryTool): excluded from the pair
> 6 request(s) unscored for baseline, 6 for memory (e.g. personalized is not scored for a planner without MemoryTool): excluded from the pair
> ORACLE requests (built from held-out targets): upper bound, not a real query log

## completion_tokens

| group | n_pairs | unscored (base/mem) | baseline | memory | diff [CI] | run-std (b/m) | W/L/T | verdict |
|---|---|---|---|---|---|---|---|---|
| oracle | 6 | 0/0 | 159.833 | 168.333 | +8.500 [-14.167, +37.667] | 27.813/29.934 | 3/3/0 | inconclusive |
| oracle/cold_text | 2 | 0/0 | 161.500 | 165.500 | +4.000 [-8.500, +16.500] | 25.456/52.326 | 1/1/0 | inconclusive |
| oracle/cold_text/cold | 2 | 0/0 | 161.500 | 165.500 | +4.000 [-8.500, +16.500] | 25.456/52.326 | 1/1/0 | inconclusive |
| oracle/constrained | 4 | 0/0 | 159.000 | 169.750 | +10.750 [-23.250, +49.000] | 28.991/18.738 | 2/2/0 | inconclusive |
| oracle/constrained/sparse | 2 | 0/0 | 169.250 | 165.250 | -4.000 [-25.000, +17.000] | 49.851/18.738 | 1/1/0 | inconclusive |
| oracle/constrained/warm | 2 | 0/0 | 148.750 | 174.250 | +25.500 [-21.500, +72.500] | 8.132/18.738 | 1/1/0 | inconclusive |
| realistic | 14 | 0/0 | 142.536 | 166.786 | +24.250 [-4.607, +59.536] | 53.185/67.983 | 8/6/0 | inconclusive |
| realistic/ambiguous | 6 | 0/0 | 56.667 | 46.417 | -10.250 [-27.083, +6.750] | 21.213/11.667 | 2/4/0 | inconclusive |
| realistic/ambiguous/none | 6 | 0/0 | 56.667 | 46.417 | -10.250 [-27.083, +6.750] | 21.213/11.667 | 2/4/0 | inconclusive |
| realistic/personalized | 4 | 0/0 | 282.875 | 359.875 | +77.000 [-9.500, +154.000] | 144.780/195.338 | 3/1/0 | inconclusive |
| realistic/personalized/sparse | 2 | 0/0 | 325.500 | 332.000 | +6.500 [-49.500, +62.500] | 108.894/237.588 | 1/1/0 | inconclusive |
| realistic/personalized/warm | 2 | 0/0 | 240.250 | 387.750 | +147.500 [+110.500, +184.500] | 180.666/153.089 | 2/0/0 | inconclusive |
| realistic/similar | 4 | 0/0 | 131.000 | 154.250 | +23.250 [-3.250, +49.750] | 9.546/25.102 | 3/1/0 | inconclusive |
| realistic/similar/sparse | 2 | 0/0 | 136.750 | 151.000 | +14.250 [-8.000, +36.500] | 15.910/29.698 | 1/1/0 | inconclusive |
| realistic/similar/warm | 2 | 0/0 | 125.250 | 157.500 | +32.250 [+1.500, +63.000] | 3.182/20.506 | 2/0/0 | inconclusive |

> ORACLE requests (built from held-out targets): upper bound, not a real query log
> n=14 < 20: too few pairs for a reliable estimate
> n=2 < 20: too few pairs for a reliable estimate
> n=4 < 20: too few pairs for a reliable estimate
> n=6 < 20: too few pairs for a reliable estimate

## llm_latency_seconds

| group | n_pairs | unscored (base/mem) | baseline | memory | diff [CI] | run-std (b/m) | W/L/T | verdict |
|---|---|---|---|---|---|---|---|---|
| oracle | 6 | 0/0 | 9.940 | 8.835 | -1.105 [-8.414, +8.094] | 6.544/2.764 | 2/4/0 | inconclusive |
| oracle/cold_text | 2 | 0/0 | 6.223 | 13.289 | +7.066 [-4.148, +18.281] | 3.983/5.005 | 1/1/0 | inconclusive |
| oracle/cold_text/cold | 2 | 0/0 | 6.223 | 13.289 | +7.066 [-4.148, +18.281] | 3.983/5.005 | 1/1/0 | inconclusive |
| oracle/constrained | 4 | 0/0 | 11.799 | 6.607 | -5.191 [-12.139, +2.389] | 7.825/1.643 | 1/3/0 | inconclusive |
| oracle/constrained/sparse | 2 | 0/0 | 8.679 | 8.844 | +0.165 [-5.054, +5.384] | 3.546/2.298 | 1/1/0 | inconclusive |
| oracle/constrained/warm | 2 | 0/0 | 14.918 | 4.371 | -10.547 [-14.501, -6.593] | 12.104/0.989 | 0/2/0 | inconclusive |
| realistic | 14 | 0/0 | 12.247 | 11.426 | -0.821 [-9.019, +5.242] | 7.646/5.253 | 8/6/0 | inconclusive |
| realistic/ambiguous | 6 | 0/0 | 14.729 | 10.931 | -3.798 [-22.470, +9.494] | 10.223/5.928 | 3/3/0 | inconclusive |
| realistic/ambiguous/none | 6 | 0/0 | 14.729 | 10.931 | -3.798 [-22.470, +9.494] | 10.223/5.928 | 3/3/0 | inconclusive |
| realistic/personalized | 4 | 0/0 | 13.240 | 15.039 | +1.799 [-1.351, +4.949] | 7.687/7.176 | 2/2/0 | inconclusive |
| realistic/personalized/sparse | 2 | 0/0 | 18.250 | 19.317 | +1.067 [-2.547, +4.680] | 9.569/9.098 | 1/1/0 | inconclusive |
| realistic/personalized/warm | 2 | 0/0 | 8.230 | 10.762 | +2.531 [-0.156, +5.219] | 5.806/5.254 | 1/1/0 | inconclusive |
| realistic/similar | 4 | 0/0 | 7.531 | 8.557 | +1.025 [-2.154, +3.910] | 3.740/2.318 | 3/1/0 | inconclusive |
| realistic/similar/sparse | 2 | 0/0 | 8.602 | 7.340 | -1.262 [-3.446, +0.922] | 4.276/4.171 | 1/1/0 | inconclusive |
| realistic/similar/warm | 2 | 0/0 | 6.461 | 9.774 | +3.312 [+1.719, +4.906] | 3.204/0.465 | 2/0/0 | inconclusive |

> ORACLE requests (built from held-out targets): upper bound, not a real query log
> n=14 < 20: too few pairs for a reliable estimate
> n=2 < 20: too few pairs for a reliable estimate
> n=4 < 20: too few pairs for a reliable estimate
> n=6 < 20: too few pairs for a reliable estimate
