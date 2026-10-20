# Ranking evaluation results

## Protocol

- Dataset: `multi_domain`, validation split, seed 42.
- Fixed sample: 1,000 users in each of cold, sparse, and warm segments (3,000 total).
- Candidates: generated once from popularity, ItemCF (5 latest fit-history seeds), and SemanticSearch (3 titles from fit history); `union_rr` and `union_all` persisted in `candidate_lists.jsonl`.
- Each scoring variant receives the same candidates per user and merge strategy. K values: 5, 10, 20.
- ItemKNN: 20 neighbors, refit on the fit split. Corpus was built in memory from configured metadata because the existing SQLite corpus failed source fingerprint validation. No corpus/cache file was written.
- Ranking metrics use validation targets not already present in that user's fit history. Target interactions already in fit are excluded from ranking relevance and reported separately. No LLM or oracle target metadata was used.
- Runtime recorded by evaluator: 1,138.10 seconds. Python 3.12.2, numpy 2.5.4, pandas 3.0.6, scipy 1.18.1, pyarrow 18.1.0.
- Reproduction command (run from `src`):

  ```powershell
  $env:PYTHONPATH='.'
  .\.venv\Scripts\python.exe scripts/evaluation/ranking_eval.py --eval-on validation --per-segment 1000 --seed 42 --candidate-budget 100 --seed-items 5 --query-items 3 --neighbors 20 --ks 5,10,20 --popularity-weights 0,1e-6,1e-4,1e-3,1e-2 --no-prebuilt-corpus
  ```

## Scorer comparison at K=10

Primary candidate scorer is the current `BaselineScorer` popularity weight `1e-6`. The 0.01 candidate changes only this weight.

| Merge | Segment | Baseline NDCG | Weight 0.01 NDCG | Baseline Recall | Weight 0.01 Recall | Baseline Hit | Weight 0.01 Hit | Rank latency baseline → 0.01 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| union_rr | cold | 0.003658 | 0.003658 | 0.006247 | 0.006247 | 0.023 | 0.023 | 0.364 → 0.368 ms |
| union_rr | sparse | 0.001807 | 0.002170 | 0.003167 | 0.003167 | 0.005 | 0.005 | 5.143 → 5.502 ms |
| union_rr | warm | 0.000938 | 0.000990 | 0.001000 | 0.001000 | 0.003 | 0.003 | 5.260 → 5.511 ms |
| union_all | cold | 0.003658 | 0.003658 | 0.006247 | 0.006247 | 0.023 | 0.023 | 0.408 → 0.383 ms |
| union_all | sparse | 0.001807 | 0.002170 | 0.003167 | 0.003167 | 0.005 | 0.005 | 5.918 → 5.851 ms |
| union_all | warm | 0.000938 | 0.000990 | 0.001000 | 0.001000 | 0.003 | 0.003 | 6.154 → 6.330 ms |

Paired, user-level bootstrap (5,000 resamples; seed 7201) for weight 0.01 versus current weight:

| Segment | Δ NDCG@10 | 95% CI | Δ Recall@10 | Δ Hit Rate@10 | Δ MRR@10 | Decision |
|---|---:|---:|---:|---:|---:|---|
| cold | 0 | [0, 0] | 0 | 0 | 0 | no effect |
| sparse | +0.000363 | [0, +0.000958] | 0 | 0 | +0.000678 | small, uncertain gain |
| warm | +0.000051 | [0, +0.000153] | 0 | 0 | +0.000167 | small, uncertain gain |

The interval lower bounds are zero, and Recall/Hit Rate do not move. Keep the current scorer; the evidence is not strong enough to promote weight 0.01.

## Retrieval and deterministic chain

At a source budget of 100, the persisted `union_all` has unseen-target recall of 0.02072 / 0.03530 / 0.02925 for cold / sparse / warm, versus 0.02072 / 0.02291 / 0.01792 for budget-matched `union_rr`. The larger union returns about 239 / 271 candidates per sparse / warm user, versus 100 for `union_rr`, and costs more to rank. This is retrieval coverage, not an improvement in final top-10 ranking quality.

The deterministic end-to-end path in this experiment is candidate retrieval/merge → `RecoModelTool` → `QueryTool`; metadata fetch succeeded for every evaluated top-K list. `union_all` should remain a candidate for separately validated latency/quality trade-offs. The experiment does not use the LLM planner.

Semantic retrieval is the measured latency bottleneck: mean 379 ms (p95 954 ms) in sparse and 269 ms (p95 535 ms) in warm; ItemCF mean is about 1.0–1.1 ms. Ranking takes about 5–6 ms for sparse/warm lists. Candidate filtering removed approximately 0.57% of raw unique candidates in sparse and 0.88% in warm due to same-user seen items; no model-unscored candidate loss occurred.

## Follow-up status

- The prior SQLite corpus was rejected because its recorded source fingerprints do not match current metadata. This run therefore uses an in-memory rebuild with complete metadata coverage.
- LLM planner evaluation was not run: `LLM_API_KEY` and `LLM_BASE_URL` are absent in the environment, and the existing `agent_eval/exp_004` artifacts are not a valid synchronized baseline. Configure and health-check an endpoint before a separate planner study.
- Git commit metadata in this environment is not available in the experiment record; source fingerprint, config, sample IDs, mapping hash, split file sizes and timestamps are recorded.
