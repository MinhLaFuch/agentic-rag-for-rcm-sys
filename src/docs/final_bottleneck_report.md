# Final Bottleneck Report: Retrieval Embedding, ANN & Ranking

- **Date**: 2026-11-22
- **Bundle**: `multi_domain_v2_audit_20261030` (`temporal_train_core`, `historical_static_catalog`, 2,637,776 items across Electronics / Toys_and_Games / Video_Games)
- **Embedding artifact**: `src/experiments/embedding_builds/minilm_v2_audit_cpu/artifact` (`sentence-transformers/all-MiniLM-L6-v2`, rev `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, 384-d float32, build ID `06ffb18aef332c384056df5d8885da436bd210b0f8e0a2886f0f7b74a79b507a`)
- **Overall verdict (v2 updated 2026-11-22)**: **Retrieval performance, ANN startup, Gate 3 (on both 3,000 validation and 3,000 held-out test users), multi-signal LTR reranking, and Vietnamese-to-English cold-query retrieval are all verified and PASS.** Remaining structural ceiling is post-cutoff catalog-cold targets (~17% of test users).

## 1. Evidence Chain (Verified Artifacts)

| Stage | Artifact | Status | Key Verified Finding |
|---|---|---|---|
| P0 Readiness | `src/experiments/readiness/p0_profile_20261116_182515.json` | PASS | `ready_for_evaluation=true`, 45 artifact checks & 27 config snapshots MATCH, 0 cross-split duplicate events |
| Full Embedding | `src/experiments/embedding_builds/minilm_v2_audit_cpu/artifact` | PASS | 2,637,776 x 384 finite unit-norm vectors (644 chunks), checksums verified |
| ANN Latency Gate | `src/experiments/retrieval_matrix/ann_validation_sq8_20261121_225014` | **PASS** | `hnsw_sq8` (M=32, efSearch=1024, 500 seeded catalog warmup, 2-pass): p50=`0.027s`, **p95=`0.057s` <= `0.100s`**, Recall@200 & NDCG@10 delta vs exact = **`0.0`** across all segments (~75x faster than exact scan p95 `4.24s`) |
| Validation Retrieval Matrix | `src/experiments/retrieval_matrix/val_sq8_p300_20261121_234849` | FAIL (warm CI low) | 900 users (300/seg): `fused - bm25` Recall@100 = `+0.01081` CI `[+0.00373, +0.01810]` (PASS), latency p95=`2.18s <= 3.5s` (PASS), warm CI low `-0.010 < -0.005` (FAIL; warm mean `+0.00481`) |
| Validation Ranking Replay | `src/experiments/ranking_eval/exp_010` | COMPLETE | Fixed-pool replay (budget=100, 900 users): `fused + HybridScorer(w=4.0)` reaches NDCG@10=`0.00555` (+151% vs `fused + BaselineScorer` `0.00221`; +113% vs `bm25 + BaselineScorer` `0.00260`) |
| Runtime Integration & Smoke | `src/tests/tools/retrieval/test_runtime_hybrid_smoke.py` + `multi_domain_v2_audit_20261030.runtime_winning.overlay.yaml` | PASS | 279 tests passed (5 FAISS skipped in baseline venv). Valid query, cold user, empty query, missing metadata, tight filters, bad artifact & unavailable encoder (strict + logged fallback) verified |
| Final Held-Out Test Retrieval | `src/experiments/retrieval_matrix/final_test_sq8_p300_20261122_093422` | FAIL (CI width) | 900 users (300/seg, fit=`train+validation`, frozen config): `fused - bm25` Recall@100 = `+0.00738` CI `[+0.00047, +0.01494]` (positive, below `0.002` CI-low threshold), latency p95=`3.00s <= 3.5s` (PASS), sparse CI low `-0.0063 < -0.005` |
| Final Held-Out Test Ranking | `src/experiments/ranking_eval/exp_011` | COMPLETE | Fixed-pool replay (budget=100, 900 users, `eval_on=test`): `hybrid + HybridScorer(w=4.0)` leads at NDCG@10=`0.00249` (+80% vs `bm25 + baseline` `0.00138`); `fused + HybridScorer(w=4.0)` yields NDCG@10=`0.00147`, Recall@10=`0.00444` (+166% vs `bm25 + baseline` `0.00167`) |
| **v2 SparseBM25 + Persisted HNSW SQ8** | `src/experiments/bm25_builds/multi_domain_v2_audit_20261030` + `src/experiments/ann_builds/minilm_v2_audit_hnsw_sq8_m32` | **PASS** | BM25 p95 drops `2.08–2.92s -> 0.26–0.39s` (**7.4x faster**); ANN startup drops `458–557s -> 3.4–5.9s` (**95x faster**); `retrieval_total` p95 `<= 0.50s` |
| **v2 Validation Matrix (3,000 users)** | `src/experiments/retrieval_matrix/val_fast_v2_p1000_20261122_134346` | **PASS (Gate 3)** | 5-source RRF (`+domain_cat_pop`): `fused - bm25` R@100=`+0.01639` CI `[+0.01199, +0.02104]`, all 3 segments strictly positive, p95=`0.359s <= 0.50s` |
| **v2 LTR Reranker (5-fold CV)** | `src/experiments/rerankers/ltr_histgbdt_v2_p1000_20261122_134346` | **PASS** | 16-feature `HistGradientBoostingClassifier` (5-fold user-grouped CV on 3,000 val users): NDCG@10=`0.00613` (+119% vs `BaselineScorer` `0.00280`, +27.4% vs `HybridScorer(w=4.0)` `0.00481`), wins on all 3 segments |
| **Track B Vietnamese Cold Queries** | `src/experiments/cold_query_track_b/vi_cold_40_20261122_180543` | **PASS** | 40 Vietnamese queries (diacritics + no-diacritics) over 2.00M eligible items: `VietnameseQueryTranslator` + `vi_bridge_hybrid` lifts NDCG@10 from `0.059–0.098` (raw) to **`0.801`**, P@10=`0.798`, Hit@10=`0.925`, p95=`151–166ms` |
| **v2 Final Held-Out Test Matrix (3,000 users)** | `src/experiments/retrieval_matrix/final_test_v2_p1000_20261122_191827` | **PASS (Gate 3)** | 3,000 test users (1,000/seg, fit=`train+validation`, frozen config): `fused - bm25` R@100=`+0.00652` CI `[+0.00350, +0.00971]`, all 3 segments strictly positive CI low, p95=`0.488s <= 0.50s`, 0 errors |
| **v2 Final Held-Out Test Ranking (3,000 users)** | `src/experiments/ranking_eval/exp_012` | **PASS** | `fused + ltr_reranker` (trained strictly on validation) leads overall: **NDCG@10=`0.00193`** (+112% vs `bm25 + baseline` `0.00091`, +52% vs `fused + hybrid_w4` `0.00127`), **NDCG@5=`0.00187`**, **Recall@10=`0.00340`** (+295%), wins all 3 segments on `fused` |

## 2. Validation vs Held-Out Test Metrics (Budget=100, 900 Users = 300/Segment)

### Retrieval Recall@100 (`recency_weighted`)

| Source | Val All | Val Cold | Val Sparse | Val Warm | Test All | Test Cold | Test Sparse | Test Warm |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `popularity` | `0.01423` | `0.01094` | `0.01500` | `0.01676` | `0.00809` | `0.00778` | `0.00537` | `0.01111` |
| `item_cf` | `0.00241` | `0.00000` | `0.00333` | `0.00389` | `0.00374` | `0.00000` | `0.00667` | `0.00456` |
| `bm25` | `0.00509` | `0.00000` | `0.00167` | `0.01361` | `0.00389` | `0.00000` | `0.00667` | `0.00500` |
| `dense` (`hnsw_sq8`) | `0.00343` | `0.00000` | `0.00167` | `0.00861` | `0.00278` | `0.00000` | `0.00333` | `0.00500` |
| `hybrid` (BM25+Dense RRF) | `0.00380` | `0.00000` | `0.00167` | `0.00972` | `0.00389` | `0.00000` | `0.00667` | `0.00500` |
| `fused` (4-source RRF) | **`0.01590`** | **`0.01094`** | **`0.01833`** | **`0.01843`** | **`0.01127`** | **`0.00778`** | **`0.01370`** | **`0.01233`** |

### Fixed-Pool Ranking NDCG@10 / Recall@10 (`exp_010` Val vs `exp_011` Test)

| Pool + Scorer | Val N@10 | Val R@10 | Test N@10 | Test R@10 | Test Cold N@10 | Test Sparse N@10 | Test Warm N@10 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `bm25 + baseline` | `0.00260` | `0.00398` | `0.00138` | `0.00167` | `0.00000` | `0.00210` | `0.00204` |
| `bm25 + hybrid_w4` | `0.00256` | `0.00398` | `0.00179` | `0.00167` | `0.00000` | `0.00333` | `0.00204` |
| `hybrid + baseline` | `0.00239` | `0.00324` | `0.00219` | `0.00278` | `0.00000` | `0.00333` | `0.00323` |
| `hybrid + hybrid_w4` | `0.00234` | `0.00324` | **`0.00249`** | `0.00278` | `0.00000` | `0.00333` | **`0.00415`** |
| `fused + baseline` | `0.00221` | `0.00337` | `0.00134` | `0.00356` | `0.00096` | `0.00234` | `0.00071` |
| `fused + hybrid_w4` | **`0.00555`** | **`0.01201`** | `0.00147` | **`0.00444`** | **`0.00100`** | `0.00111` | `0.00230` |

### Latency Breakdown (Held-Out Test, `final_test_sq8_p300_20261122_093422`)

- `ann_search` (`hnsw_sq8`): p50=`0.029s`, p95=`0.076s` (`<= 0.100s` gate holds on test too)
- `dense_encode` (MiniLM CPU): p50=`0.021s`, p95=`0.039s`
- `item_cf`: p50=`0.004s`, p95=`0.020s`
- `bm25` (SQLite FTS5 `indexed_topk`): p50=`1.169s`, **p95=`2.916s`** (~97% of `retrieval_total` p95=`2.999s`)
- `RankTool` (`exp_011`): p95 ~ `20-30ms`/user

## 3. What Was Solved vs Remaining Bottlenecks

### Solved
1. **Verified data/provenance pipeline & full-catalog embeddings**: 2.64M items encoded with reproducible manifest/checksums; strict provenance guards in both `candidate_recall.py` and `ranking_eval.py`.
2. **Dense search latency bottleneck**: Replaced 3.9-4.2s exact scan and memory-contending HNSW Flat with `hnsw_sq8` + seeded catalog warm-up (`p95 = 0.033-0.076s`, zero quality loss vs exact).
3. **Unified evaluation & runtime integration**: `ranking_eval.py` now replays frozen retrieval matrices directly with strict hash checks and supports hybrid `SearchTool`; `LiveBackend` & `build_tools` support `HybridScorer` + hybrid `SearchTool` with strict benchmark failure mode and explicit logged `bm25_fallback` runtime mode.
4. **Consistent improvement of `HybridScorer(w=4.0)` over `BaselineScorer` on every pool**: On held-out test, `hybrid_w4` beat `baseline` on `bm25` (`0.00179` vs `0.00138`), `hybrid` (`0.00249` vs `0.00219`), and `fused` (`0.00147` vs `0.00134` NDCG@10; `0.00444` vs `0.00356` Recall@10).

### Unresolved Bottlenecks (Why the Problem Is Not Marked Fully Closed)
1. **Catalog-cold / post-cutoff targets (~16-19% hard ceiling)**: On validation `148/900` (16.4%) and on test `171/900` (19.0%) users have *all* held-out targets appearing after `as_of_timestamp` (`all_targets_ineligible`). Any causally valid retriever has zero recall on these users.
2. **Cold users without history (~76-80% of cold segment has `no_input`)**: History-title proxy (`Track A`) cannot test dense retrieval for cold users. **Track B (independent natural-language cold-query dataset, including VI->EN queries)** was not created, so no claim is made that embeddings solve cold-start queries.
3. **Limited standalone gain of `all-MiniLM-L6-v2` on history-title proxy**: At budget=100, `hybrid` vs `bm25` delta is `-0.00130` (val) and `0.00000` (test), though on test `hybrid` pool produced higher ranking NDCG@10 (`0.00249` vs `0.00179` with `hybrid_w4`) because dense+BM25 RRF surfaced higher-ranked hits. Most of `fused`'s Recall@100 gain (`+0.0108` val, `+0.0074` test) comes from combining `popularity` + `item_cf` + `bm25` + `dense`.
4. **High variance / low absolute hit count at 300 users/segment**: On test, `fused - bm25` Recall@100 is positive across all 3 segments (`+0.0078` cold, `+0.0070` sparse, `+0.0073` warm), yet formal Gate 3 failed on CI lower bounds (`all` CI low `+0.00047 < 0.002`, `sparse` CI low `-0.0063 < -0.005`) due to sparse binary hit counts (`13/900` fused hits at K=100 on test).
5. **SQLite FTS5 BM25 latency**: BM25 (`p95 = 2.08-2.92s`) now accounts for >95% of retrieval wall time; optimizing dense/ANN further will not meaningfully reduce end-to-end latency.
6. **Fused pool dilution under Top-10 ranking on test**: On test, `fused` has ~3x higher Recall@100 (`0.01127`) than `hybrid` (`0.00389`), yet `hybrid + hybrid_w4` achieves higher NDCG@10 (`0.00249`) than `fused + hybrid_w4` (`0.00147`) because popularity-heavy fused candidates dilute lexical/semantic hits in Top-10 (`9/13` fused hits dropped below Top-10).

## 4. Recommended Next Actions

1. **Build Track B (cold-query benchmark)** with explicit user queries (Vietnamese & English) and relevance judgments to evaluate multilingual/semantic retrieval where history proxy cannot.
2. **Address BM25 latency** (e.g., query-token cap/pruning or replacing SQLite FTS5 OR expansion with a dedicated lexical index) before scaling to >1,000 users/segment.
3. **Learn a dedicated reranker** (e.g., LightGBM/LambdaMART or cross-encoder using per-source ranks, dense cosine score, BM25 score, CF similarity, and popularity) to convert `fused`'s 3x higher candidate recall into Top-10 NDCG without popularity dilution.
4. **Test domain-adapted or multilingual bi-encoders** (e.g., `bge-m3` / `multilingual-e5`) if Vietnamese queries are a primary target, keeping the same verified evaluation contract.
## 5. Phase A–D Upgrade Summary (v1 -> v2 on Held-Out Test)

| Metric (Held-Out Test, `recency_weighted`, budget=100) | v1 (`exp_011` / 900 users) | v2 (`exp_012` / 3,000 users) | Change |
|---|---:|---:|---|
| Gate 3 Status | `FAIL` | **`PASS`** | All 3 segments CI95 low > 0 |
| ANN Startup (`hnsw_sq8`) | `557.4s` (in-memory build) | **`5.88s`** (persisted load) | **95x faster** |
| BM25 p95 Latency | `2.916s` (SQLite FTS5) | **`0.393s`** (`SparseBM25Index`) | **7.4x faster** |
| `retrieval_total` p95 Latency | `2.999s` | **`0.488s`** | **6.1x faster** |
| `fused` Recall@100 vs `bm25` | `+0.00738` CI `[+0.00047, +0.01494]` | **`+0.00652` CI `[+0.00350, +0.00971]`** | Tighter CI, passes `>= 0.002` |
| Top-10 NDCG on `fused` (`baseline` -> `hybrid_w4` -> `ltr_reranker`) | `0.00134 -> 0.00147` | **`0.00095 -> 0.00127 -> 0.00193`** | **+103% vs baseline, +52% vs `hybrid_w4`** |
| Top-5 NDCG on `fused` (`hybrid_w4` -> `ltr_reranker`) | `0.00000` | **`0.00021 -> 0.00187`** | **8.9x higher** (resolves Top-10 dilution) |
| Vietnamese Cold Queries NDCG@10 (40 VI queries, diacritics & no-diacritics) | `0.059–0.098` (raw) | **`0.801`** (`vi_bridge_hybrid`, p95 `151–166ms`) | **>8–10x gain** |

### Remaining Structural Notes
- **Post-cutoff catalog-cold targets**: `511/3,000` (17.0%) held-out test users still have all targets appearing after `as_of_timestamp` (`all_targets_ineligible`) — an inherent temporal ceiling.
- **Vietnamese cross-lingual coverage**: `VietnameseQueryTranslator` handles common e-commerce phrases and brand/model passthrough deterministically (`< 1ms`), complemented by the Planner LLM for free-form requests; full zero-dictionary Vietnamese vector search would require re-encoding all 2.64M items with a multilingual bi-encoder (e.g. `intfloat/multilingual-e5-small` or `BAAI/bge-m3`).
