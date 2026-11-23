# Retrieval → Ranking Bottleneck Analysis

**Date:** 2026-11-19 · **Bundle:** `multi_domain` (`temporal_train_core` protocol) · **Status:** investigation complete — dominant loss is **candidate retrieval**, ranking/score issues are secondary but real

**Audience:** discussion doc for another agent. Everything needed to reproduce or extend the analysis is referenced by path.

---

## UPDATE 2026-11-19 (later) — per-request funnel CORRECTS the priority

`pool_stage_report.py` on campaign_005 scored.jsonl (exp_5 planner, 152 scored rows):

- `best_stage` per target: **retrieve=124, pool=39 — ZERO targets reach `rank_input` or beyond**
- Per-path `stage_lost`: itemcf:retrieve=60, sql:retrieve=44, semantic:retrieve=20 (pool losses: itemcf 51, sql 29, semantic 29)
- `target_in_any_path_pool` (catalog membership) was high (82–100%) — but that measures "item exists in visible catalog", NOT "tool returned it"

**Revised conclusion:** the DOMINANT loss is **candidate retrieval** — SearchTool(BM25, limit 50)/FilterTool(SQL, limit 100)/SimilarTool(itemcf, top_k 20) candidate lists essentially never contain held-out targets (consistent with exp_002 recall@100 ≈ 0.02–0.03). Targets die at `retrieve` stage before RankTool ever sees them.

The RankTool/scorer findings below remain valid but are **SECONDARY** — they matter once retrieval recall improves enough for targets to reach ranking. Fix order: (1) candidate recall (per-source recall/query formulation, long-tail CF coverage — union measured as null, §8.A.1; tool limits measured as non-bottleneck, §6.1), (2) then retrieval-score blending in RankTool.

---

## UPDATE 2026-11-22 — scorer A/B + Q2 categorization: both live-tested, both NEGATIVE

**Learned scorer (`mode: learned`, affine [pop, cf] weights 1.82/-9.98/-0.16,
`package/tools/scoring/learned_scorer.py`):** offline injection evidence was
strong (4-6× baseline rescue@10, `q6_scorer_comparison_v4.json`) but the live
A/B (`experiments/agent_eval/learned_scorer/exp_5` vs
`filter_ab/exp_2_baseline`, identical 152 requests/seed) was net-negative on
every target metric — cold_text task_success 0.65→0.45, target_reachable
0.50→0.143; personalized recall@10 0.025→0. Injection rescue measures only
"target in top-10" and cannot see whole-list quality costs: the negative CF
weight demotes the personalization signal. **`scoring.yaml` reverted to
`mode: baseline`**; `LearnedScorer` + `learned` mode remain wired/tested for
future refits — do not enable without a new live A/B.

**Q2 inferred categories:** embedding kNN assigned top-1 voted categories to
229,975 uncategorized items (gated variant: 53,333 at vote_share≥0.30).
Both live evals (`filter_ab/exp_3`, `exp_4`) were net-negative vs baseline —
guessed categories pollute popularity-ordered category-filter pools even at
high confidence (exp_4 target_reachable cold_text 0.118 vs 0.50 baseline).
**Layer disabled**; artifact kept at
`investigations/item_categories_inferred_gated.parquet`.

**F10 baselines (`experiments/baselines/exp_001`, 50k users):** popularity
recall@10 0.0077 > item_knn 0.0055 > bpr_mf 0.0054 — CF track closed; no
learned CF variant beats popularity for held-out targets. Numeric path is
now device-flexible (CUDA with CPU fallback): BPR-MF `_fit` + fused top-k on
GPU, exact O(n) top-k replacing per-row lexsort, `eval_user_sample` config.
Full run ~15min (was 6h+ stalled).

**Net:** retrieval remains the dominant bottleneck; ranking-side learned
interventions tested to date do not survive live A/B. Remaining levers:
retrieval enrichment (query formulation, multilingual embeddings — user's
eval pending), temporal `first_seen` proxy caveat, eval protocol (Q23
sample-size decisions).

---

## 1. Dataset & data pipeline

### 1.1 Source dataset

- **Amazon Reviews 2023** (McAuleley lab), 3 domains: `Video_Games`, `Toys_and_Games`, `Electronics`
- Item id = namespaced `{domain}::{parent_asin}` (`original_item_id` = ASIN)
- Metadata per item: `title`, `store` (closest field to brand), `price` (REAL, NULL ~55% in Video_Games), `average_rating`, `rating_number`, `main_category` + `categories` (hierarchy, stored separately), `first_seen_ts` = min interaction timestamp (**proxy, not launch date**)
- Corpus meta: `resource/corpus/multi_domain/corpus_multi_domain.meta.json` — coverage 1.0 all domains, `first_seen_protocol: minimum_timestamp_per_namespaced_item_in_all_cleaned_interactions_v1`, `metadata_temporal_validity: first_seen proxy only; static metadata validity unverified`

### 1.2 Splits — temporal, no random

`configs/data/split.yaml`, protocol `temporal_train_core`:

| Split | Rows | Cutoff |
|---|---|---|
| train | 48,766,894 | ≤ 1,617,737,606,134 ms |
| validation | 7,787,433 | ≤ 1,651,701,127,817 ms |
| test | 7,511,892 | > cutoff_2 |

- Users: 23,332,162 · Items: **2,637,776** (full catalog) · fit_core (ItemKNN training subset): 19,471,576 rows
- Manifest + hashes: `resource/splits/multi_domain/stage_3.manifest.json` — P0 readiness `experiments/readiness/p0_multi_domain_20261117_160642.json` = ready, no blockers
- Domain item counts: Electronics 1,609,860 · Toys_and_Games 890,667 · Video_Games 137,249

### 1.3 Corpus (what tools query)

`resource/corpus/multi_domain/corpus_multi_domain.sqlite` (~3.2 GB in memory):

- `items` table = `ITEM_COLUMNS`: item_id, domain, original_item_id, first_seen_ts, title, store, price, average_rating, rating_number, main_category (`package/data/_schema.py`)
- `items_fts` = SQLite FTS5 over title/store/main_category/categories → BM25 via `bm25(items_fts)`
- `item_categories` = category hierarchy (used by FilterTool `categories_any/all`)
- **Temporal visibility**: `first_seen_filter` metadata policy — items with `first_seen_ts` after the eval `as_of` are hidden from tool queries. Verified on 196 validation targets: 160/196 visible at train_end, 36/196 first-seen during validation (cold/unreachable by design), 0 after validation end.

### 1.4 Target visibility sanity check (done, data is NOT corrupt)

- 196/196 inspected validation targets exist in corpus
- 70.4% of targets are in `train_core` (487,420 items — the ItemKNN/scoreable subset)
- Global popularity top-10 hits only 1/116 users; mean popularity-rank percentile of targets = 0.265 → **targets are mid/long-tail, not head items**

---

## 2. Agent pipeline (what the planner actually calls)

```
user request (kind: similar | personalized | cold_text | exclusion | ambiguous | unanswerable)
  → planner LLM (template or llm inference) generates query + tool calls
  → retrieval tools return candidates (item_id lists, some carry `score`)
  → planner is INSTRUCTED to ALWAYS call RankTool on candidates
       (package/agents/planner/_prompt.py:19-20)
  → RankTool re-scores with HybridScorer → top_k
  → LookupTool fetches details → final recommendations
```

Tool limits — `configs/agent/tools.yaml` → `package/tools/_limits.py`:

| Tool | Path | Default limit | Max |
|---|---|---|---|
| SearchTool (BM25 [+dense RRF]) | `package/tools/retrieval/search_tool.py` | 50 | 1000 |
| FilterTool (SQL) | `package/tools/sql/filter_tool.py` | 100 | 1000 |
| SimilarTool (ItemKNN CF) | `package/tools/ranking/similar_tool.py` | 20 | 1000 |
| RankTool | `package/tools/ranking/rank_tool.py` | all scorable | — |
| QueryTool | — | 20 rows | 100 |

Runtime wiring: `scripts/evaluation/run_agent_eval.py:579-624`.

---

## 3. Query layer — how text becomes candidates

### 3.1 SearchTool (the "semantic"/BM25 path)

`package/tools/retrieval/search_tool.py`:

- `_tokenize` → English stopword removal, porter stemming (`_helper.py`); **max 20 tokens** (`semantic_max_query_tokens`)
- FTS5 MATCH = **OR over all tokens** (`"t1" OR "t2" ...`, line 125) — permissive; relies on `bm25()` ranking
- SQL: `items_fts JOIN items`, `ORDER BY -bm25, rating_number DESC, item_id`, `LIMIT` (default 50)
- Optional filters via shared `compile_filters` (domain, price, rating, categories_any/all, store, title_contains, exclude_item_ids) — same keys as FilterTool
- Candidates carry `score` = negated bm25 (higher = better) + full item columns

**Weakness:** OR-matching on a 2.6M-item catalog → `total_matches` can be huge; top-50 by bm25 is a needle-in-haystack filter. Query tokens come from planner-generated English keywords — quality depends on planner, not verified.

### 3.2 Dense leg (opt-in)

- `dense_retrieval.enabled: true` in `configs/eval/dense_retrieval.yaml`; artifacts `experiments/embedding_builds/multi_domain_semantic` (format-A converted from `multi_domain_full`)
- Encoder lock: `all-MiniLM-L6-v2@1110a243`, dim 384, 2,637,776 vectors
- SearchTool: dense `vector_store.search(query_vec, limit*2)` → RRF fusion `1/(60+rank)` over BM25+dense union → top `limit`
- Fail-closed: enabled + missing torch/artifacts → raise, no silent BM25 fallback

### 3.3 FilterTool ("sql" path)

Parameterized SQL over `items`+`item_categories`; default `ORDER BY rating_number DESC` → returns **most-rated items matching filters**, NOT relevance-ranked. For text-ish requests the planner must translate intent into categories/price — a planner capability bottleneck.

### 3.4 SimilarTool ("itemcf" path)

ItemKNN similarity matrix lookup on seed items → top_k=20 similar items with `similarity` score. Only works when seeds are known core items. **Verified (`similar_tool.py:109`):** candidates = union of the top-k neighbor rows of the *seed items only* (`similarity[seed_idx]`) — it does NOT score the user's full history. A target is reachable only if it sits in the top-20 neighbor list of one planner-chosen seed (~≤200 candidates total). The full user-history CF ranking (`user_items @ similarity` over all ~486k core items) exists inside `BaselineScorer`/`ItemKNNRecommender.recommend` but is **not exposed as a retrieval tool** — there is currently no way to generate "top-N items for this user by CF" candidates.

---

## 4. Embedding layer

- **Model:** sentence-transformers `all-MiniLM-L6-v2` rev `1110a243`, 384-dim (`experiments/embedding_builds/encoder.lock.json`)
- **Document text protocol:** `title_store_main_category_categories_sorted_v2` → `"{title}. Store: {store}. Main: {main_category}. Categories: {sorted cats}."` (`package/embeddings/format_catalog_text.py`)
- **Query side:** raw query text embedded directly — **format mismatch**: docs are structured `title | store | main | cats`, queries are free text → embedding-space gap (consistent with dense ≈ BM25 in recall)
- Build: format-B full build `multi_domain_full` → converted format-A `multi_domain_semantic`; `build_dense_retrieval.py` fail-closed on missing deps
- Offline evidence (`candidate_recall` exp_002, validation, 1000 users/segment, recall@100):

| Source | cold | sparse | warm |
|---|---|---|---|
| popularity | 0.020 | 0.018 | 0.020 |
| item_cf | 0 | 0.001 | 0.007 |
| semantic (BM25) | 0 | 0.003 | 0.010 |
| hybrid (BM25+dense RRF) | 0 | 0.004 | 0.008 |
| union_all | 0.020 | 0.022 | 0.033 |
| union_hybrid_all | — | 0.0229 | 0.0308 |

→ Dense did **not** beat BM25 on this proxy; kept as opt-in ablation. Note: this proxy embeds *history-derived* queries, not planner text queries — planner-query recall is unmeasured.

---

## 5. Scoring & ranking layer

### 5.1 RankTool

`package/tools/ranking/rank_tool.py`:

- Input: `candidates` list — **only `item_id` is consumed** (`candidate_ids()`); the `score` SearchTool attached is **stripped**
- `exclude_seen=true` default: drops items in `scorer.seen_items(user_idx)` (user history)
- Temporal policy: candidates failing `first_seen_filter` at eval as_of → moved to `unscored`
- `unscored_item_ids`: items not in `item2id` or outside model matrix → excluded from ranking entirely
- Output `ranked`: `argsort(-score, stable)` → top_k; ties keep input order

### 5.2 Scorer actually used — `configs/agent/scoring.yaml` → `mode: baseline`

**Correction (2026-11-20):** campaign_005 and the union A/B ran `BaselineScorer`, not `HybridScorer` (`scoring.mode: baseline`; hybrid is opt-in). Actual formula (`baseline_scorer.py:95-102`):

```
score(item) = pop_norm[item] * 1e-6  +  cf_score(user,item)        # cf = user_items[user] @ similarity, UNNORMALIZED
```

- `pop_norm` = popularity / max popularity (tiny 1e-6 weight — pure tiebreak)
- CF term is the **raw** ItemKNN similarity sum (no per-user peak normalization — unlike HybridScorer's `/peak`)
- **No retrieval/BM25/dense score is an input** — query relevance never reaches the ranker
- Measured on trajectories (`scripts/evaluation/ranktool_score_audit.py`, `ranktool_score_audit.json`):
  - exp_5: 92 RankTool steps / 19,921 candidates → **97.0% have cf == 0**; **58.7% of rank-1 picks have cf == 0** (decided by popularity tiebreak, not personalization); 79.6% of all candidate scores are exactly 0.0
  - union run: 93 steps / 16,424 candidates → 96.3% cf_zero, 59.1% top1_cf_zero — identical profile
- `HybridScorer` (pop_norm×4.0 + cf/per_user_peak, `hybrid_scorer.py`) exists for `mode: hybrid` comparisons but was NOT what produced these numbers

### 5.3 Model coverage — `build_core_model.py`

- ItemKNN fit on `train_core` only: core items ≈ 487,420 vs catalog 2,637,776 → **~82% of catalog has similarity=0** in the remapped model; popularity array is core-derived → non-core items score ~0 (pop_norm×1e-6 ≈ 0) → always sorted last → `top_k` effectively restricted to core items
- **Consequence:** the long-tail/cold items that motivated the 4× catalog rebuild can never be recommended through the RankTool path
- `similarity` matrix is core×core cosine kNN; `user_items` uses full pre-cutoff history

### 5.4 Planner mandate

`configs/agent/prompts.yaml` (`planner.system_prompt`) instructs the planner to ALWAYS rank retrieved candidates with RankTool → the BM25/dense relevance signal computed in SearchTool is discarded on every planner run.

---

## 6. Where targets actually die — stage funnel evidence

Stage taxonomy (`score_layer1_outcome.py:304-313`): `pool`(0) → `retrieve`(1) → `rank_input`(2) → `rank_unscored`/`rank_excluded_seen`(3) → `rank_topk`(4) → `final`(5) → `survived`(6)

**campaign_005, exp_5 (planner, template, reflect=0, multi_turn) — 152 scored rows:**

```
best_stage per target:  retrieve=124   pool=39   (rank_input+: ZERO)
per-path stage_lost:    itemcf:retrieve=60  sql:retrieve=44  semantic:retrieve=20
                        itemcf:pool=51  sql:pool=29  semantic:pool=29
```

Per-kind `target_in_any_path_pool` (catalog membership): similar 37/40, personalized 33/40, exclusion 14/16, cold_text 20/20 — high, but that is NOT tool retrieval.

**Interpretation:** targets exist in the visible catalog but tool candidate lists (BM25 top-50 / SQL top-100 by rating / itemcf top-20) essentially never contain them → they die at `retrieve` before RankTool sees them. Consistent with exp_002 recall@100 ≈ 0.02–0.03 at much larger k.

Also observed: `retrieved_count` mean 567 for personalized (FilterTool returning hundreds of candidates) yet zero contain targets → **volume ≠ recall**; ordering/filter choice determines whether targets are in the list at all.

### 6.1 Planner query replay — measured 2026-11-20 (`scripts/evaluation/planner_query_replay.py`)

Re-executed every recorded SearchTool/FilterTool/SimilarTool call offline (same corpus, `historical_static_catalog`, as_of=1617737606549, same dense artifacts + ItemKNN core model), then re-ran with budgets 200/500. Report: `planner_replay_report.json`.

| run | requests w/ targets | retrieval steps | fidelity ok/mismatch | hits in recorded cands | hits @ budget 500 |
|---|---|---|---|---|---|
| exp_5 (planner, template, r0) | 116 | 88 | 86 / 2 | **0** | 4 (best rank 154–280, median 208) |
| exp_9 (planner+memory, template, r0) | 116 | 82 | 69 / 13 | **0** | 1 (rank 154) |
| exp_11 (planner+memory, llm, r0) | 116 | 90 | 75 / 15 | **0** | 1 (rank 347) |
| exp_12 (planner+memory, llm, r1) | 116 | 87 | 74 / 13 | **0** | 1 (rank 46) |
| exp_10 | — | — | run incomplete (no requests.jsonl) | — | — |

**Conclusions (measured):**

- **Budget cutoff is NOT the loss.** Raising limits to 500 surfaces targets in only 5/464 request-runs, all via SearchTool at ranks 46–347. The dominant loss is upstream: planner queries + retriever genuinely do not return targets — i.e. F1 is a query/retrieval-recall problem, not a `limit` problem.
- **SimilarTool contributes zero hits at any budget** — structural: ~20 neighbors/seed cap and ItemKNN core covers only 487k/2.64M items, so non-core targets have no CF path at all.
- **Fidelity caveat:** the ~13–15 "mismatches" per memory-planner run are a *logging artifact*, not retriever nondeterminism — trajectory args for multi-seed SimilarTool calls are serialized as truncated strings (`"<list length=10 first_3=[...]>"`), so those steps cannot be re-executed. Recorded candidates are still used for hit analysis (all zero). exp_5's 2 mismatches are the same class.
- Planner-query quality vs `category_oracle` upper bound: ~~full 3,000-user run~~ **killed after ~4h15m (2026-11-20), no output saved** — the 90-user probe (exp_003, same seed prefix) + `oracle_recall_diagnostic` + `category_sql_recall` already answered the directional question (§6.6, §8.A.3); rerun only if statistical precision is needed.

### 6.2 Pool-stage loss decomposition — the temporal ceiling (measured 2026-11-20)

`best_stage` counts `target_stage_detail` per target in exp_5 `scored.jsonl` (171 scored targets):

| best_stage | count | share | meaning |
|---|---|---|---|
| `retrieve` | 124 | 72.5% | catalog-visible, tools missed |
| `pool` — catalog-invisible | 29 | 17.0% | `first_seen_ts > as_of` → absent from TEMP `items` view (`apply_metadata_policy.py:123`) → invisible to SearchTool AND FilterTool |
| `pool` — other | 10 | 5.8% | visible in catalog but no path eligible (itemcf pool-blocked etc.) |
| none | 8 | 4.7% | target idx unresolvable in id2item |

**`first_seen_ts` is a proxy** = minimum timestamp per item across cleaned interactions, NOT a launch/availability date (stated in the policy record itself). An item that existed on Amazon but had no cleaned interaction before the cutoff is hidden — so ~17% of targets are **unwinnable in this eval regardless of retriever quality**. This is partly by-design point-in-time simulation, but the proxy is conservative: a real system at time T can surface items with zero prior interactions.

**Eval-validity caveat for the report:** recommend a sensitivity run (`candidate_recall.py --metadata-policy snapshot` or `no_filter`) to measure how much recall the temporal filter itself costs. Do NOT "fix" this in code — it's a protocol decision.

**Pool semantics** (`score_layer1_outcome.py:240-270`): sql/semantic pool = membership in the policy-filtered corpus `items` table; itemcf pool = nonzero column in the ItemKNN similarity matrix AND (when temporal policy active) corpus-visible. `target_in_any_path_pool` = existential OR across paths — hence the earlier warning that it measures eligibility, not retrieval hits.

**Net ceiling:** ~17% invisible-by-policy + itemcf-blocked share ⇒ even a perfect retriever cannot exceed ~75–80% target reachability under `historical_static_catalog`. The 72.5% `retrieve` losses remain the dominant *fixable* problem.

### 6.3 Why the tools are structurally limited (code-verified)

- **Session is NOT a union pool.** `plan_executor.py:217` collects `session.candidates` only from FilterTool + SearchTool (**SimilarTool excluded**), capped at `session.max_candidates=100`, and it is cross-turn prompt state — RankTool only sees what the planner passes via `"$N.candidates"` (one step's output). A robust union needs run-level accumulation inside `_execute` across all 3 tools, preserving per-source scores for Direction B.
- **ItemKNN core-only is deliberate.** `stage_3.manifest.json`: `data_protocol=temporal_train_core`, `fit_core_min_item_pairs=5`, `fit_core_min_user_pairs=5` — a k-core density filter on the *train* split only. Items with <5 train interactions (~82% of catalog) get no neighbors → SimilarTool returns nothing AND RankTool scores them flat 0.0. Open question: raise coverage (retrain on full train) vs add a separate long-tail candidate source.
- **RankTool drops retrieval score by design-limitation.** `candidate_ids()` keeps only `item_id`; SearchTool's `score` (negated BM25) never reaches the scorer. Campaign_005 ran `BaselineScorer` (`pop_norm×1e-6 + unnormalized CF`, §5.2); `HybridScorer` (`pop×4 + cf/peak`) exists but is opt-in via `scoring.mode: hybrid`. With core-only CF, non-core candidates get ~0 signal → popularity order.

### 6.4 Target × ItemKNN-core coverage (measured 2026-11-20)

`scripts/evaluation/target_core_coverage.py` (`target_core_coverage.json`) cross-tabs each target's `best_stage` against core membership (nonzero column in the ItemKNN similarity matrix; 485,803/2,637,776 items ≈ 18% are core):

**exp_5 (163 stage-resolved targets):**

| best_stage | core | non_core |
|---|---|---|
| `retrieve` (visible, missed) | **112** | 12 |
| `pool` | 0 | 39 |

Union A/B run shows the same shape (102 core / 11 non_core at `retrieve`; 45 non_core at `pool`).

**Two consequences:**

1. **The dominant retrieve loss is among CORE items** — 112/124 (90%) of visible-but-missed targets DO have CF neighbors. "Long-tail CF coverage" (Direction A.4 retrain-on-full-train) would only address the 12 non-core retrieve losses + is irrelevant to the 39 pool losses (already invisible).
2. **All `pool`-stage targets are non-core** — consistent with the first_seen proxy (§6.2): items with <5 train interactions tend to have late first_seen → invisible under `historical_static_catalog`. Core filtering and temporal visibility are correlated failure modes for the same long tail.

### 6.5 User-level CF top-N ceiling — measured ~0 (2026-11-20)

`scripts/evaluation/cf_topn_recall.py` (`cf_topn_recall.json`) computed the hypothetical "top-N items for this user by full-history CF" (`user_items[user] @ similarity`, seen items excluded — the ranking that exists inside `BaselineScorer` but is exposed by NO tool):

- **0 / 163 targets have any nonzero CF score** for their user — recall@10/20/50/100/500 = 0.000 across every `best_stage` and every `kind` (similar, personalized, cold_text, exclusion)
- Root cause is sparsity, not tooling: e.g. user_idx 2865112 has only **4 history items** in `user_items` → cf vector has ~80 nonzero entries. ItemKNN k=20 means each history item contributes ≤20 neighbors → the entire CF candidate space per user is a few hundred items out of 486k core — held-out targets essentially never land in it
- **Consequence:** Direction A.4 options (a) user-level CF top-N tool and (b) SimilarTool `use_history` mode would surface ~nothing — the ItemKNN signal itself cannot recall these targets. CF-based candidate generation needs a fundamentally different model (MF/two-tower, Direction B.4) or much larger k, not just a new tool wrapper
- This also retroactively explains the 97% cf_zero RankTool audit (§5.2): it's the same sparsity — candidates drawn from BM25/FilterTool rarely coincide with the user's ~80-item CF neighborhood

### 6.6 Why oracle recall is only ~10% — per-leg diagnosis (2026-11-20)

`scripts/evaluation/oracle_recall_diagnostic.py` re-ran the exp_003 oracle queries per-target at k=1000 (`oracle_recall_diagnostic.json`):

- **Catalog ceiling:** only **74.2%** of the 155 targets are visible under `historical_static_catalog` (40 invisible — consistent with §6.2)
- **Visible-only recall@200:** BM25 7.0%, dense 7.0%, hybrid(RRF) 6.1%; **75% of visible targets rank >1000 in BM25**, 89% >1000 in dense
- **Query truncation:** oracle queries average ~21 raw tokens (p90=42, max=74) vs `semantic_max_query_tokens=20` — multi-target users lose whole categories to the cap
- **Dense leg is NOT better than BM25** here (dense @1000 = 11.3% vs BM25 25.2%) — the query/doc format mismatch (F4) is real

`scripts/evaluation/category_sql_recall.py` then measured the source `candidate_recall` does NOT cover — **FilterTool-style exact-category SQL** (`category_sql_recall.json`):

| approach | recall@200 | recall@1000 |
|---|---|---|
| pooled-all-categories + popularity (naive union) | ~0% | ~0% |
| oracle BM25 / hybrid (exp_003) | ~5–10% | ~18% |
| **FilterTool single-category, best cat** | **21.3%** | **40.0%** |

- Per-target best category (mean 3.2 cats/target to choose from): 6 targets ≤50, 27 in 51–200, 11 in 201–500, 18 in 501–1000; **42/155 targets have NO category rows at all** (unreachable by any category filter)
- **Caveats:** "best_cat" is oracle — assumes the planner picks the right one of ~3 candidates; FilterTool agent limit is 100 rows (recall@100 ≈ ~10%); broad multi-category `EXISTS+ORDER BY` queries **exceed the 5s `sql_time_budget`** (observed SQLTimeOutError) — production FilterTool needs narrow filters
- **Conclusion:** structured category filtering is the strongest measured candidate source (~4× oracle-BM25 at @200) — the loss is partly that the planner doesn't issue precise single-category filters, and `candidate_recall` never measured this path

### 6.7 Stage-isolation injection — would ranking have saved the targets? (2026-11-20)

`scripts/evaluation/ranktool_injection_probe.py` (`ranktool_injection_exp5.json`, `ranktool_injection_union.json`) answers the counterfactual the funnel cannot: each request's held-out targets were **appended to the real union of recorded retrieval candidates** (targets last, so input-order tiebreaks don't favor them) and passed through the **real RankTool.execute** — same BaselineScorer, same `historical_static_catalog` policy, `exclude_seen=True`, full ranking.

exp_5 results (116 requests with targets, 196 targets):

| fate | n | % |
|---|---|---|
| `ranked` (scored, not filtered) | 160 | 81.6% |
| `hidden_policy` (first_seen filter) | 36 | 18.4% |
| `seen_excluded` | **0** | 0% |
| `unscored_other` | 0 | 0% |

- **Fate breakdown confirms the funnel independently:** the 18.4% hidden fraction matches the §6.2 pool-stage estimate (~17%); zero seen-exclusions because held-out targets are future interactions, never in train history.
- **Rescue among ranked targets:** @1=37, @5=59, **@10=74 (46%)**, @20=124 (78%), @50=146 (91%); median rank 11.5, p90≈40, max 1009.
- **BUT conditioned on real competition** (86 requests with non-empty retrieval union; 126 ranked targets): **@10 = 40 (31.7%)**, @20 = 90 (71%), @50 = 112 (89%), median rank 16. The remaining 30 requests had *empty* retrieval unions — their "rescue" is trivial (targets vs nothing).
- **Decisive ranking finding: `cf_nonzero_frac_ranked = 0.000`** — every single injected target scored **purely on the popularity term** (`pop_norm×1e-6`). ItemKNN contributes literally zero signal for held-out targets (§6.5 confirmed at the RankTool level, not just the hypothetical tool level). Target ranks are therefore popularity ranks within the candidate set — no personalization whatsoever.
- **Implication:** even under oracle retrieval, BaselineScorer would surface only ~1/3 of targets at top-10, and *which* third is decided by popularity, not relevance. F2 is upgraded from "latent risk" to **measured second bottleneck**: retrieval fixes alone cap at ~32% top-10 rescue unless scoring changes too (retrieval-score blending / better CF / HybridScorer).
- **Union A/B run confirms:** identical fates (160 ranked / 36 hidden), conditioned rescue @10 = 35/115 = **30.4%** vs exp_5's 31.7% — a larger candidate pool does not change the popularity-only outcome.

### 6.8 ItemKNN structural ceiling — exact co-occurrence probe (2026-11-20)

`scripts/evaluation/itemknn_cooccurrence_probe.py` (`itemknn_cooc_exp5.json`) computed the **exact** binary-cosine `sim(h,t) = |U_h ∩ U_t| / √(|U_h|·|U_t|)` over `train_core` for every (history item h, held-out target t) pair, and compared each sim against h's stored top-20 similarity threshold. This measures whether *any* ItemKNN parameterization could surface the targets — not just the current k=20.

exp_5 results (175 mapped targets):

| metric | value |
|---|---|
| targets in fit-core at all | 122/175 (69.7%) — 53 have no CF path by construction |
| core targets sharing **any** train_core user with a history item | **47/122 (38.5%)** |
| targets exceeding a history item's top-20 threshold (`entered_k20`) | **0** — sanity check reproduces the cf=0 finding exactly |
| `max_ratio` = sim ÷ top-20 threshold | median 0.0, p90 0.25, p99 0.54, **max 0.91** |
| targets with ratio > 0.5 / > 0.1 | 2.5% / 24.6% |

- **Interpretation:** for ~62% of core targets the co-occurrence signal is *literally absent* — no user in train_core touched both the target and any history item, so no kNN variant (any k, any train split) can score them. For the remainder, the best sim reaches only ~25% of the top-20 threshold at p90 — entering top-20 would need roughly **k ≈ 80–500+** neighbors/item, and even then CF scores would be tiny.
- **Verdict: ItemKNN is structurally hopeless for this eval, not just under-parameterized.** The held-out targets are precisely the items *lacking* co-interaction signal — which is also why they're hard to retrieve. CF-based candidate generation or scoring requires a fundamentally different model (MF / two-tower / content-aware), not a bigger ItemKNN.

### 6.9 Planner FilterTool audit — the best source is unusable in production (2026-11-20)

Trajectory audit of exp_5 + union run (every SearchTool/FilterTool/SimilarTool step):

**Usage:**
- FilterTool called 41× (exp_5) / 45× (union); **~70% with EMPTY `filters:{}`** → unfiltered `ORDER BY rating_number DESC` popularity dump (30/41 and 27/45 ok)
- Successful nonempty filters are domain-only or exclusion constraints — **never a leaf category**
- **Category-filtered calls: 7 (exp_5) + 8 (union) = 15 total, ZERO succeeded**
  - 4× `NonExistentCategory999` — intentional unanswerable-probe requests (correct rejections)
  - 3× real leaf categories (`Enclosures`, `Running GPS Units`, `Arm & Wristband Accessories`) on `cold_text` requests — **all failed with SQL time budget**, even though the request's own `category` field supplied the exact valid catalog name
  - Rest: planner-invented `categories_exclude` key (rejected — doesn't exist), misc
- **Target hits across ALL recorded retrieval outputs: 0** — no target ever appeared in any candidate list the planner saw, from any tool
- Secondary planner errors: SearchTool time-budget failures 6×/13× per run; FilterTool timeouts 3× per run

**Root cause (code-verified, reproduced):**
- `compile_filters.py:280` emits a **correlated `EXISTS`** on `item_categories`; `filter_tool.py:85-89` emits `ORDER BY rating_number ... ` with the LIMIT applied *outside* (`item_corpus.select` wraps `SELECT * FROM (...) LIMIT ?`)
- Measured: `categories_any=['Enclosures'] LIMIT 100` takes **38.6s** on the 2.6M-item corpus (vs 5s `sql_time_budget`) — SQLite scans `items` evaluating EXISTS per row, then sorts all matches
- `FilterTool.execute` then calls `corpus.count(where)` — a **second** full scan that would also blow the budget even if select passed
- Ironically the category names ARE valid: `'Enclosures'` exists verbatim in `item_categories`; `category_exists`/`suggest_categories` validation passes — the query plan is the only failure
- **Second latent bug found during the fix:** under `historical_static_catalog`/`snapshot`, `apply_metadata_policy` rebuilds `item_categories` as a TEMP table indexed **only on `item_id`** — no `category` index — so even an uncorrelated rewrite would full-scan ~10M rows for `categories_all`/`GROUP BY` queries

**FIX IMPLEMENTED + VERIFIED (2026-11-20, uncommitted):**
- `compile_filters.py`: `categories_any`/`categories_all` now emit **uncorrelated IN-subqueries** (`items.item_id IN (SELECT ... WHERE category IN ...)`; `categories_all` via `GROUP BY item_id HAVING COUNT(DISTINCT category)=N`) — semantically identical WHERE, but SQLite materializes the small category match set once via the category index instead of probing per `items` row
- `apply_metadata_policy.py`: added `idx_temp_item_categories_category` on the temp `item_categories` table in **both** policy branches (`no_filter` + `historical_static_catalog`/`snapshot`)
- Measured on the real corpus (`historical_static_catalog`, as_of=1617737606549): `categories_any=['Enclosures']` **timeout → 0.37s** (3,421 visible matches); multi-cat 0.38s; `categories_all` real pair **timeout → 2.86s**; empty-result `categories_all` 0.40s; SearchTool keyword+category filter 0.76s; 366 sql/tools/component tests pass
- **Residual:** `categories_any=['Electronics']` (1.48M-item mega-category) still exceeds 5s — inherent to sorting ~1.5M matches; acceptable since `domain` filter is the right tool there, and the timeout error already tells the planner to narrow

**Why this matters:** §6.6 measured single-category FilterTool as the strongest candidate source (r@200=21.3%, r@1000=40% — ~4× oracle-BM25). **That source was 100% unusable as implemented** — every attempt timed out. With the SQL fix it now runs in <1s; remaining gap is planner behavior (~70% of FilterTool calls still use empty `filters:{}` popularity dumps; it also invents `categories_exclude` and hits SearchTool timeouts 6–13×/run). Next: prompt/tooling to issue precise leaf-category filters, then A/B on the same 152-request set.

---

## 7. Findings (revised priority)

### F1 — DOMINANT: candidate retrieval recall ≈ 0 (retrieve-stage loss)

- SearchTool OR-query top-50 on 2.6M items; FilterTool orders by `rating_number` (popularity proxy, not relevance); SimilarTool limited to core-item neighborhoods
- Per-request evidence (§6.1–6.4): 72.5% of targets are catalog-visible yet die at `retrieve`; ZERO reach ranking; budget 500 changes almost nothing (5/464)
- **90% of those retrieve losses are CORE items** (§6.4) — they have CF neighbors yet no tool surfaces them. And §6.5 shows even a hypothetical full-history CF top-N source recalls **0/163 targets** — ItemKNN's signal is too sparse (~80 nonzero scores/user) to generate these candidates by ANY mechanism
- This is a **recall@k-at-tool-limit** problem: even perfect ranking can't recover a target that never enters the candidate list
- **Ceiling caveat:** ~17% of targets are additionally unwinnable under `historical_static_catalog` (first_seen proxy, §6.2) — report absolute numbers with this caveat

### F2 — RankTool discards query relevance; ranking is CF-starved — **UPGRADED TO MEASURED SECOND BOTTLENECK (§6.7)**

- `BaselineScorer` (the mode campaign_005 actually ran, §5.2) = pop_norm×1e-6 + **unnormalized** CF sum; SearchTool's `score` stripped by `candidate_ids()`
- Measured (`ranktool_score_audit.py` on exp_5 + union trajectories): **97% of RankTool candidates have cf == 0**; **~59% of rank-1 recommendations are decided by the popularity tiebreak, not personalization**; 79.6% of candidate scores are exactly 0.0
- **Stage-isolation injection (§6.7):** with targets injected into real candidate sets, **100% of ranked targets have cf == 0** — they rank on popularity alone; only **31.7% reach top-10** against real competition (median rank 16). Retrieval fixes alone cap at ~⅓ top-10 rescue — scoring MUST change alongside retrieval (retrieval-score blending, HybridScorer, or better CF)
- Sparse/cold users → CF≈0 → ranking ≈ popularity ordering regardless of query

### F3 — ~82% of catalog has no CF signal in the model

- Root cause confirmed (§6.3): `train_core` = k-core filter (≥5 train pairs per user AND item, `temporal_train_core` protocol) → 487,420/2,637,776 items get neighbors; the rest score ~0 → always last → top_k restricted to core
- Long-tail value of the rebuilt bundle unreachable via RankTool AND SimilarTool paths
- ~~Open quantification~~ **DONE (§6.4):** 112/124 `retrieve` losses are core items, 12 non-core; all 39 `pool` losses are non-core
- ~~Would a different ItemKNN fix it?~~ **NO — §6.8 exact co-occurrence probe:** 62% of core targets share zero train_core users with any history item (signal absent, not truncated); best sim reaches only ~25% of the top-20 threshold at p90 → needs k≈80–500+ AND still scores near zero. ItemKNN is structurally hopeless for held-out targets

### F4 — secondary issues

- BM25 OR-query noise (≤20 tokens, oracle queries avg ~21 → truncation); dense query/doc format mismatch (dense ≤ BM25 measured, §6.6); ItemKNN similarity learned on core only while user_items is full-history; **planner FilterTool usage unmeasured** — §6.6 shows single-category filters are the strongest source, so whether the planner issues them is now the key open question
- Exclusion-kind recall capped ~14% of requests (targets sharing excluded leaf category — quantified, mild)
- **NEW:** `first_seen_ts` proxy hides ~17% of targets at `pool` stage (§6.2) — eval ceiling, not a code bug; trajectory logger truncates multi-seed `items` args (breaks replay fidelity, §6.1)

---

## 8. Fix directions (reordered)

**Direction A — candidate recall (do first):**

1. **Union retrieval sources per request** — ✅ IMPLEMENTED + MEASURED 2026-11-20 (uncommitted): `$union.candidates` pseudo-reference in `_resolve_refs` merges deduped candidates from all ok SearchTool/FilterTool/SimilarTool steps (first-seen order, score-carrying duplicates preferred, `retrieved_by` tags, cap `max_candidates`); planner prompt prefers it for multi-source plans; `session.candidates` now includes SimilarTool; `_simplify_args_for_log` keeps id-lists whole (fixes trajectory replay fidelity).
   - **A/B result** (`experiments/agent_eval/union_ab/exp_1_union_prompt/run_1`, same 152 requests as exp_5, planner+template+reflect0): planner adopted union in **89/93 ok RankTool steps** (verified: `candidate_item_ids` == exact union of prior retrieval outputs). **Zero targets reached `rank_input`** — `best_stage` still only `retrieve`/`pool`. recall/precision/hit_rate remain 0.000 across kinds; `task_success` deltas (exclusion 0.20→0.45, cold_text 0.50→0.25) are planner-run variance, not target recall.
   - **Conclusion:** union works as designed and is strictly a superset, but confirms the §6.1 prediction — with every source missing, pooling doesn't create recall. It remains useful substrate (bigger RankTool input once sources improve) but is NOT a fix by itself.
2. ~~Raise tool limits~~ — **measured 2026-11-20 (§6.1): NOT the bottleneck.** Budget 500 vs recorded ~50/100 surfaces targets in only 5/464 request-runs; loss is query/retrieval recall, not cutoff. FilterTool ordering by `rating_number` remains a popularity proxy — fix is query/filter formulation, not limit size
3. **Query formulation — first oracle-vs-history signal (exp_003 probe, 2026-11-20):** `candidate_recall.py --query-mode category_oracle --retrieval hybrid --per-segment 30` (90 users, strict subset of exp_002's seed-42 sample) vs exp_002 `history` baseline (3,000 users):

   | source | history r@200 (cold/sparse/warm) | oracle r@200 |
   |---|---|---|
   | hybrid alone | 0.000 / 0.004 / 0.012 | 0.067 / 0.100 / 0.044 |
   | union_hybrid_all | 0.028 / 0.030 / 0.041 | 0.094 / 0.100 / 0.103 |

   Oracle queries lift recall@200 roughly **2–3×** (union_all: ~0.03→~0.10) → **planner query quality is a real, recoverable loss component** — but the oracle ceiling itself is only ~10% recall@200, so retriever capability remains the harder bound. Caveats: 30 vs 1,000 users/segment (noisy), oracle uses held-out categories (upper bound, not achievable verbatim). Full 3,000-user oracle run was killed (~4h, no output) — probe numbers stand as the directional estimate.
   - **Sharpened by §6.6 + §6.9:** FilterTool single-category filtering measures recall@200 = 21.3% / @1000 = 40% (vs ~7% BM25) — the strongest measured source — **but §6.9 shows it is 100% unusable in production**: all 15 category-filtered calls across both runs failed (SQL time budget; measured 38.6s vs 5s budget for one leaf category, plus a second full-scan `count()`). **Fix order is now: (a) rewrite the category-filter SQL plan in `compile_filters`/`filter_tool`/`item_corpus.count` so the EXISTS+ORDER BY executes in seconds, (b) then prompt/tooling so the planner actually issues precise leaf-category filters** (it currently uses empty `filters:{}` ~70% of the time; its rare real attempts — including request-supplied `category` values — all timed out). Also note 42/155 targets have no category rows → category path can't cover them; BM25/dense still needed for the uncategorized tail.
4. **CF candidate generation — CLOSED, now proven structurally (§6.5 + §6.8):** user-level CF top-N recall = 0.000 at all k; the exact co-occurrence probe shows ~62% of core targets share *zero* train_core users with history items (no signal exists to retrieve) and the best sim reaches only ~25% of the top-20 threshold at p90. No ItemKNN parameterization fixes this — held-out targets are items *lacking* co-interaction signal by construction. Remaining CF option: fundamentally different model (MF/two-tower, Direction B.4) — a research decision, not a quick fix
5. **Eval-validity sensitivity**: rerun `candidate_recall.py` with `--metadata-policy snapshot`/`no_filter` to quantify the ~17% first_seen ceiling (§6.2) — needed for honest absolute numbers in the report

**Direction B — ranking/score (after retrieval improves):**

1. Blend retrieval score into RankTool: preserve `score` from candidates, `score = w_ret·norm(retrieval) + w_pop·pop_norm + w_cf·cf_norm`, configurable weights, new `scorer_mode` for A/B
2. Non-core items then compete via retrieval score instead of flat 0.0 → unlocks long-tail
3. Dense query encoding: same structured format as docs, or instruction prefix; re-measure recall
4. Longer-term: MF/two-tower CF on full 48.7M train interactions instead of core-only ItemKNN

---

## 9. Verification plan

1. `pool_stage_report.py <run_dir>` per run — stage funnel before/after any fix (script: `scripts/evaluation/pool_stage_report.py`)
2. `candidate_recall.py --retrieval {bm25|dense|hybrid|union_*}` for source-level recall (exp_002 baseline)
3. Unit: scorer returns blended scores; non-core item with high retrieval score outranks zero-signal core item
4. `run_agent_eval` smoke (template mode, per_segment=5) → `task_success_relevant` vs `task_success` gap
5. Full campaign subset → compare `task_success_relevant` across scorer modes

---

## 10. Evidence paths

- Stage funnel: `scripts/evaluation/pool_stage_report.py` + `experiments/agent_eval/campaigns/campaign_005/*/run_1/scored.jsonl` (`target_stage_detail`, `stage_lost`, `target_in_pool_*`, `retrieved_by_*`)
- Recall numbers: `experiments/candidate_recall/exp_002/metrics.json`
- Scorer: `package/tools/scoring/hybrid_scorer.py`, `baseline_scorer.py`, `candidate_scorer.py`
- RankTool: `package/tools/ranking/rank_tool.py`; SimilarTool: `package/tools/ranking/similar_tool.py`
- SearchTool: `package/tools/retrieval/search_tool.py`; tokenizer: `package/tools/retrieval/_helper.py`, `tokenize_search_query.py`
- FilterTool/compile_filters: `package/tools/sql/filter_tool.py`, `package/tools/sql/compile_filters.py`
- Core model remap: `package/evaluation/recommender/analysis/build_core_model.py`
- Stage taxonomy: `package/evaluation/layer1_outcome/score_layer1_outcome.py:300-576`
- Corpus meta: `resource/corpus/multi_domain/corpus_multi_domain.meta.json`; split manifest: `resource/splits/multi_domain/stage_3.manifest.json`
- Embedding lock: `experiments/embedding_builds/encoder.lock.json`; dense config: `configs/eval/dense_retrieval.yaml`
- Tool limits: `configs/agent/tools.yaml`; split protocol: `configs/data/split.yaml`
- Planner mandate: `package/agents/planner/_prompt.py:19-20`
- Wiring: `scripts/evaluation/run_agent_eval.py:579-624`
