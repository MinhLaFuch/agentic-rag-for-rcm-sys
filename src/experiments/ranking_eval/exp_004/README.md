# exp_004

- timestamp: 2026-10-20T03:29:55.326067+00:00
- seed: 42
- git_commit: None
- runtime_seconds: 1819.9
- dataset: {"tag": "multi_domain", "splits_dir": "D:\\DACNTT\\src\\agentic-rag-for-rcm-sys\\src\\resource\\splits\\multi_domain", "eval_on": "validation", "num_users": 2757103, "num_items": 678281, "mapping_hash": "13e3e5b362225fcb912db2c1d6bb5d6ef7a728c193547f9688296c4cd3ebc848", "split_files": {"train": {"path": "D:\\DACNTT\\src\\agentic-rag-for-rcm-sys\\src\\resource\\splits\\multi_domain\\train.parquet", "size_bytes": 2132738419, "mtime_ns": 1790441165783867400}, "validation": {"path": "D:\\DACNTT\\src\\agentic-rag-for-rcm-sys\\src\\resource\\splits\\multi_domain\\validation.parquet", "size_bytes": 298978513, "mtime_ns": 1790441169496644100}, "test": {"path": "D:\\DACNTT\\src\\agentic-rag-for-rcm-sys\\src\\resource\\splits\\multi_domain\\test.parquet", "size_bytes": 296357912, "mtime_ns": 1790441173153835700}}}

All scorer variants receive identical persisted candidates per user and merge. Candidate generation uses popularity, ItemCF, and titles from fit history (realistic offline proxy). Ranking metrics use validation targets not seen in fit; target items already in fit are reported separately. This deterministic chain does not invoke the LLM planner.

## Phase 7 validation confirmation

- Protocol: `multi_domain` validation only; 2,000 fixed users per cold/sparse/warm segment (6,000 total), seed 42; ItemKNN refit on fit/train data; 5 recent fit-history seeds for ItemCF, 3 fit-history titles for semantic queries, 20 neighbors, source budget 100, K=5/10/20. Both scorer weights use the same saved candidate lists per merge. No test split or target metadata was used.
- Reproduction command (from `src`):

  ```powershell
  $env:PYTHONPATH='.'
  .\.venv\Scripts\python.exe scripts/evaluation/ranking_eval.py --eval-on validation --per-segment 2000 --seed 42 --candidate-budget 100 --seed-items 5 --query-items 3 --neighbors 20 --ks 5,10,20 --popularity-weights 1e-6,1e-2 --no-prebuilt-corpus
  ```
- Evaluator-reported runtime: 1,819.9 seconds. Full validation was not run: the complete mapped catalog has 2,757,103 users and `validation.parquet` is about 299 MB; the full evaluation was beyond this run's time budget.
- Overall K=10 values are macro averages of the three equally sized segments. Paired bootstrap uses user-level NDCG@10 differences, 5,000 resamples, seed 7201; scored item IDs were mapped through `resource/mapped/multi_domain/item2id.json`.

| Merge | Scorer | NDCG@10 | Recall@10 | Hit Rate@10 | MRR@10 |
|---|---|---:|---:|---:|---:|
| union_rr | baseline 1e-6 | 0.002368 | 0.003767 | 0.011833 | 0.003332 |
| union_rr | 0.01 | 0.002452 | 0.003767 | 0.011833 | 0.003520 |
| union_all | baseline 1e-6 | 0.002337 | 0.003684 | 0.011667 | 0.003313 |
| union_all | 0.01 | 0.002421 | 0.003684 | 0.011667 | 0.003501 |

| Segment (union_rr) | Baseline NDCG / Recall / Hit / MRR @10 | Weight 0.01 NDCG / Recall / Hit / MRR @10 | Paired delta NDCG@10 (95% CI) |
|---|---|---|---|
| cold | 0.004063 / 0.006910 / 0.026500 / 0.006121 | 0.004063 / 0.006910 / 0.026500 / 0.006121 | 0 [0, 0] |
| sparse | 0.001818 / 0.002642 / 0.005000 / 0.002300 | 0.002005 / 0.002642 / 0.005000 / 0.002656 | +0.000187 [+0.000003, +0.000490] |
| warm | 0.001223 / 0.001750 / 0.004000 / 0.001573 | 0.001288 / 0.001750 / 0.004000 / 0.001782 | +0.000065 [0, +0.000168] |

Across all 6,000 users, paired delta NDCG@10 is +0.000084 (95% CI [+0.000010, +0.000190]); 6 users improved, none worsened, and 5,994 were unchanged. Recall@10 and Hit Rate@10 are unchanged. Catalog coverage@10 is slightly lower for weight 0.01 (union_rr sparse 0.025988 to 0.025902; warm 0.025641 to 0.025578). Ranking latency is about 5.2-5.4 ms mean for sparse/warm `union_rr`; the weight change has no material latency effect. The change affects a few near-tie orderings, so statistical separation does not establish a useful product gain.

Retrieval merge comparison (same validation targets, before final ranking): `union_all` raises candidate recall versus `union_rr` from 0.02358 to 0.03273 (sparse) and 0.02003 to 0.03083 (warm), while mean sets grow from 100 to 237.9 and 270.4 candidates. Final ranking quality does not improve correspondingly: at weight 0.01, warm NDCG@10 is 0.001195 for `union_all` versus 0.001288 for `union_rr`. Semantic retrieval is the dominant latency cost (mean 443 ms sparse / 291 ms warm; p95 1.231 s / 645 ms). ItemCF mean is about 1.0-1.1 ms. The deterministic retrieval to merge to `RecoModelTool` to `QueryTool` path completed for the sample; metadata fetch success was 100%, with no ranker-level seen/unscored removals after merge. Pre-budget raw retrieval dropped 0.56% (sparse) and 0.91% (warm) as seen items.

### Regression and decision

- Full test suite: 1,002 passed, 3 skipped, 13 SciPy sparse-efficiency warnings (15.27 seconds). This includes unit, integration, contract, regression, data, agent, and demo tests. No failures.
- The full ranking evaluation exercised the deterministic end-to-end tool chain for all sampled users and both merges. LLM planner end-to-end evaluation was not run; this deterministic experiment does not invoke a provider.
- `popularity_weight=0.01`: **needs more testing**, not production-ready. Its absolute NDCG gain is tiny and concentrated in six users; Recall/Hit are flat and catalog coverage is slightly lower. Keep production at `1e-6` pending a predeclared practical-effect threshold and independent confirmation.
- `union_all`: **quality/size trade-off not accepted for final ranking**. Candidate recall improves, but candidate lists are 2.4-2.7 times larger and final warm NDCG is lower than with `union_rr`; retain as an offline retrieval-recall option only.
- Experiment provenance records `git_commit: null`; the worktree was dirty during this run. Config, sample IDs, mapping hash, source fingerprint, package versions, and split file sizes/timestamps are saved, but a clean commit-linked rerun is required before production consideration.
