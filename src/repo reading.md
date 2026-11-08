---
created: 2026-09-27-15:07
updated: 2026-11-09
viewed: 2026-11-09
branch: tools-building
commit: 0ce2ea8
---
# Project Repository Reading — agentic-rag-for-rcm-sys

**agentic-rag-for-rcm-sys / src** — An LLM-agent product recommender running on Amazon Reviews 2023 (3 domains: Video_Games, Toys_and_Games, Electronics).

> **Architectural principle:** The LLM only decides *what to do*; tools provide controlled operations; ItemCorpus provides item knowledge; recommenders provide recommendation signals; the agent layer combines results; the inference layer writes the final response using only items the agent selected.

## 1. Repository State (as of 2026-11-09)

| Item | Value |
|------|-------|
| **Repository root** | `C:\\Users\\ph181\\Documents\\Repositories\\agentic-rag-for-rcm-sys` |
| **Current branch** | `tools-building` |
| **HEAD commit** | `0ce2ea8` ("Phase 2.1: quality gate thresholds + verification fixes") |
| **Working tree** | Clean except untracked `experiments/` artifacts |
| **GitNexus index** | Re-indexed after Phase 2 (5,454 nodes / 13,038 edges) |
| **Test baseline** | 1395 passed, 0 skipped, 2 xfailed (Week 46 remediation through Phase 4) |

### Week 46 Audit Remediation Status (Phases 1–2.1 complete)

| Area | Status |
|------|--------|
| Jev evaluator error handling | Fixed — `judge_error`/`provider_error` states, no longer counted as unsupported claims |
| Grounding benchmark | Fixed — no rule-based fallback; missing `TYPESAFE_API_KEY`/Jev failure = case FAIL; judged answer is real `compose_answer` output (`evidence_kind: "real_inference_output"`) |
| Campaign runner | Fixed — auto `comparison_pairs` actually used; `campaign_id` persisted per experiment; non-metric keys (`n`) excluded |
| `_run_all.py` aggregation | Fixed — `success_rate` read from nested metrics; missing result = failed; exit code non-zero on failure; fail counts shown beside means |
| Executor benchmark | Rebuilt (Phase 4.7, D1 option 1) — real tools over fixture corpus, `_execute` scope only; infra-fault cases moved to `tests/agents/test_executor_error_taxonomy.py` |
| Component quality gates | Added — `thresholds` per component in `component_benchmarks.yaml`; `pass` separate from `success`; unconfigured = `not_evaluated` (only memory has thresholds) |
| Skipped tests | All 8 restored and passing (SQL hardening ×4, memory leakage ×2, stage4 ×2) |

### Historical: Refactor-phase-0 Changes (already merged into tools-building)

| Change Area | Before (tools-building) | After (refactor-phase-0) |
|-------------|------------------------|-------------------------|
| **Package structure** | `package/tools/{corpus,recommenders,score,sql_query,evaluation}` | `package/{corpus,recommenders,tools/{scoring,sql,ranking,retrieval,base}}` |
| **Tools** | 6 tools in `package/tools/` | 6 tools distributed: `corpus/`, `recommenders/`, `tools/{scoring,sql,ranking,retrieval,base}` |
| **Recommendation evaluation** | `package/tools/evaluation/` | `package/evaluation/recommender/` (core, metrics, experiment, config, utils) |
| **Agent evaluation** | `package/evaluation/` (root) | `package/evaluation/` + `trajectory/`, `product_reply/`, `doubles/`, `recommender/` |
| **Mock vs Real** | Separate implementations | Merged with `--mock` flag, `package/evaluation/doubles/` for test doubles |
| **Component benchmarks** | 5 components, mostly TODO | 5 components: Memory, Planner, Grounding, Integration, Executor |
| **Tests** | 1318 passed | 368 passed, 4 skipped, 6 warnings |

### Refactor Summary (Phases 0-8 Complete)

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Verify, state plan | ✅ Complete |
| 1 | Fix Baseline Issues | ✅ Complete |
| 2 | Delete Unused Code | ✅ Complete |
| 3 | Merge `package/tools/evaluation` into `package/evaluation` | ✅ Complete |
| 4 | Move `corpus`/`recommenders`/`score` out of `tools/` | ✅ Complete |
| 5 | Memory Tool Location | ✅ Complete (no changes) |
| 6 | Merge Mock and Real Implementations | ⚠️ Mostly Complete (Phase E skipped) |
| 7 | Fix Script Wrappers | ✅ Complete |
| 8 | Update Documentation | ✅ Complete |

**Overall:** Refactor complete. Phase E (MockAgentRunner replacement) skipped as optional.

---

## 2. Repository Structure

```
src/
├── configs/                              # YAML configuration (single source of truth)
│   ├── agent/                            # agent.yaml, llm.yaml, agent_eval.yaml, inference.yaml, ...
│   ├── data/                             # cleaning.yaml, filtering.yaml, split.yaml
│   ├── eval/                             # component_benchmarks.yaml, judge.yaml, baselines.yaml, ...
│   ├── evaluation/                       # campaign.yaml
│   └── path/                             # data_paths.yaml (centralized paths), domains.yaml (incl. merged_name)
├── package/                              # Main application package
│   ├── agents/                           # PlanExecutor (LLM planner), Type1Agent (fixed plan), toolkit, session
│   ├── api/                              # LLMProvider (abstract), JevProvider, build_llm_provider
│   ├── config/                           # load_config, get_data_paths, Pydantic schemas
│   ├── corpus/                           # ItemCorpus (SQLite FTS5 + BM25), build/load/save
│   ├── data/                             # Pipeline: clean → merge/filter → map/split → leakage check
│   ├── demo/                             # Gradio demo (adapter, backend, samples, view)
│   ├── evaluation/                       # 5-layer framework + component benchmarks + campaign runner
│   │   ├── recommender/                  # Core recommender evaluation (core, metrics, experiment, config, utils)
│   │   ├── doubles/                      # Test doubles: Fake*Tool, ScriptedLLM, ScriptedJudge
│   │   ├── trajectory/                   # Trajectory scoring (score_trajectory.py, summarize.py)
│   │   ├── product_reply/                # Product reply evaluation (with Jev)
│   │   ├── campaign/                     # Campaign orchestration
│   │   ├── component/                    # Component benchmarks (Memory, Planner, Grounding, Integration, Executor)
│   │   ├── layer1_outcome/               # Layer 1: Recommendation quality
│   │   ├── layer2_interaction/           # Layer 2: Output quality
│   │   ├── layer3_grounding/             # Layer 3: Faithfulness
│   │   ├── layer4_process/               # Layer 4: Planning quality
│   │   ├── layer5_deployment/            # Layer 5: Latency/cost
│   │   ├── ablation/                     # Ablation experiments
│   │   ├── campaign/                     # Campaign orchestration
│   │   ├── multi_turn/                   # Multi-turn evaluation
│   │   ├── reporting/                    # Report generation
│   │   └── provenance/                   # Run provenance tracking
│   ├── inference/                        # compose (LLM/template), grounding (claim check), outcome
│   ├── memory/                           # MemoryTool (read-only user profile from interactions)
│   ├── recommenders/                     # Popularity, ItemKNN, BPR-MF (evaluation, runtime, shared)
│   ├── tools/                            # Base protocol + 6 distributed tools
│   │   ├── base/                         # Tool protocol, ToolResult, ToolInputError, logger
│   │   ├── retrieval/                    # SearchTool (BM25/FTS5)
│   │   ├── ranking/                      # SimilarTool (ItemCF), RankTool (CandidateScorer)
│   │   ├── scoring/                      # BaselineScorer, CandidateScorer protocol
│   │   ├── sql/                          # FilterTool, LookupTool
│   │   └── utils/                        # Utilities
│   └── utils/                            # Utilities
├── scripts/                              # Entry points: run_agent_eval, run_pipeline, run_demo, ...
│   ├── data_pipeline/                    # run_pipeline.py (4 stages)
│   ├── demo/                             # run_demo.py (--mock flag)
│   ├── eda_diagnostic/                   # EDA and split diagnostics
│   ├── evaluation/                       # run_agent_eval.py, run_baselines.py, opik_poc.py
│   ├── experiments/                      # compare_experiments.py
│   ├── llm_agent/                        # smoke_real_llm.py
│   └── tools/                            # run_tools.py, check_llm_provider.py
├── tests/                                # pytest suite (config, corpus, data, agents, tools, evaluation, demo)
├── experiments/                          # Artifacts: agent_eval (exp_NNN), baselines, candidate_recall, ...
├── docs/                                 # Phase reports, refactor plans, mock/real lists
└── *.md                                  # Phase reports, audit reports, architecture docs
```

**Code convention:** One public symbol per file (file name = symbol name). Private symbols prefixed with `_`.

---

## 3. System Architecture

### 3.1 Overall Data Flow

```
User Request
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    PLANNER (PlanExecutor)                   │
│  • LLM writes full JSON plan (steps + optional ask_user)    │
│  • Tools: SearchTool, FilterTool, SimilarTool, RankTool,   │
│           LookupTool, MemoryTool                            │
│  • Reference resolution: $N.path (step N output field)      │
│  • Reflection: up to N rounds on failure / quality threshold│
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    EXECUTOR (PlanExecutor.run)              │
│  • Executes steps in order, resolves references             │
│  • Validates args, catches invented IDs, logs via ToolCallLogger│
│  • Handles tool errors, retries, reflection triggers        │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    TOOLS (6 controlled operations)          │
│  • SearchTool        — BM25/FTS5 text retrieval             │
│  • FilterTool        — Structured filter retrieval          │
│  • SimilarTool       — ItemCF (item-item collaborative)     │
│  • RankTool          — CandidateScorer (popularity/ItemKNN) │
│  • LookupTool        — Item metadata hydration (SQL)        │
│  • MemoryTool        — User profile from interaction history│
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    RECOMMENDATION FOUNDATION                │
│  • ItemCorpus (SQLite FTS5 + BM25, read-only)               │
│  • CandidateScorer protocol (BaselineScorer: pop + ItemKNN) │
│  • Recommenders: Popularity, ItemKNN, BPR-MF (evaluation)   │
│  • Provenance tracking: file_hash, mapping_hash, fit_provenance│
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    INFERENCE LAYER                          │
│  • compose_llm.py    — LLM writes answer from agent items   │
│  • compose_template.py — Deterministic template fallback    │
│  • grounding/check_grounding.py — Claim validation (bare ASIN, nums)  │
│  • Jev evaluation    — Faithfulness + communication (LLM-judge)│
└─────────────────────────────────────────────────────────────┘
    │
    ▼
Final Response (grounded, validated)
```

### 3.2 Recommendation Foundation vs. Agentic Layer

| Aspect | Recommendation Foundation | Agentic Layer |
|--------|---------------------------|---------------|
| **Components** | ItemCorpus, CandidateScorer, Recommenders (Popularity, ItemKNN, BPR-MF) | PlanExecutor, Type1Agent, Tools, MemoryTool, Inference |
| **Role** | Core recommendation signals (collaborative, content, popularity) | Planning, tool orchestration, multi-turn, grounding, explanation |
| **LLM involvement** | None (except BPR-MF training, offline) | PlanExecutor (planning), Inference (answer composition), Jev (judgment) |
| **Data flow** | Offline training → online scoring | User request → plan → tool execution → ranking → answer |

### 3.3 Agent Types

| Agent | Planning | LLM | Tools | Use Case |
|-------|----------|-----|-------|----------|
| **baseline** (ItemKNN) | Fixed (retrieve→rank→fetch) | No | SimilarTool, RankTool, LookupTool | Pure CF, no LLM cost |
| **type1** | Fixed (retrieve→rank→fetch) | No | SearchTool, RankTool, LookupTool | Text query → retrieval → ranking |
| **planner** | LLM-generated JSON plan | Yes | All 6 tools | Complex multi-step reasoning |
| **planner_memory** | LLM-generated JSON plan | Yes | All 6 + MemoryTool | Personalized with user profile |

---

## 4. Data Pipeline and Datasets

### 4.1 Amazon Reviews 2023

- **Domains**: `Video_Games`, `Toys_and_Games`, `Electronics` (configurable via `domains.yaml`)
- **Key statistics** (from Phase 2 EDA):
  - 72.21% users have only 1 interaction (cold-start dominant)
  - Sparsity: 99.9988%
  - Data split: temporal (train < validation < test) — **no random split**

### 4.2 Pipeline Stages (scripts/data_pipeline/run_pipeline.py)

| Stage | Input | Output | Description |
|-------|-------|--------|-------------|
| 1. Clean | `resource/raw/<Domain>.jsonl.gz` | `resource/cleaned/<Domain>/interactions.parquet` | Parse, normalize, dedupe, filter missing fields |
| 2. Merge/Filter | Cleaned per-domain | `resource/filtered/<tag>/interactions.parquet` | Merge domains, k-core filter (min_user=5, min_item=5), cold-start report |
| 3. Map/Split | Filtered | `resource/mapped/<tag>/{user2id,item2id}.json`, `resource/splits/<tag>/{train,validation,test}.parquet` | ID mapping, temporal split (80/10/10), leakage checks |
| 4. Artifacts | Mapped + splits | `resource/corpus/<tag>/corpus_<tag>.sqlite`, `resource/item_knn/<tag>/item_knn_<tag>_<eval_on>.npz` | Build ItemCorpus (SQLite FTS5), ItemKNN similarity matrix |

**Leakage prevention**: Profile snapshot at timestamp `t` only uses interactions ≤ `t` (enforced in `MemoryTool`, `RankTool`, evaluation).

### 4.3 Item ID Format

- **Namespaced**: `{domain}::{parent_asin}` (e.g., `Video_Games::B071HMD7CM`)
- **No plain-ID mode** — same ASIN in different domains = different items
- **Corpus stores domain as column** — never parsed from ID string

---

## 5. Recommendation Foundation

### 5.1 Embedding — **NOT IMPLEMENTED**

**Status**: `package/tools/embeddings/__init__.py` explicitly states "NOT IMPLEMENTED"

- Current retrieval: **SQLite FTS5 + BM25** over `title`, `store`, `main_category`, `categories` (lexical only)
- No embedding model integration found in codebase
- BPR-MF recommender uses embeddings internally but is separate from candidate retrieval
- Future work documented: select multilingual model, design indexing, evaluate vs. FTS5/BM25 baseline

**Implication**: Retrieval is purely lexical. Vietnamese queries must be translated to English (catalog is English). Semantic gap for cold users with no interaction history.

### 5.2 Retrieval

**Implementations**:
1. **SearchTool** — BM25/FTS5 free-text search (English keywords required). Supports structured filters (domain, price, rating, categories, store). Returns candidates with BM25 score.
2. **FilterTool** — Pure structured filter retrieval (no text query). Same filter keys as SearchTool.
3. **SimilarTool** — ItemCF: given seed items, returns similar items from precomputed ItemKNN similarity matrix.

**Query preprocessing**: `_tokenize` (lowercase, \w-only, ASCII-fold for Unicode). Tokens double-quoted for FTS5 safety.

**Candidate generation**: Tools return `candidates` list with `item_id`, metadata, and `score` (BM25 or similarity). Planner combines via `$N.path` references.

**Top-K**: Configurable per tool, capped at `MAX_CANDIDATES` (default 100). `SEMANTIC_DEFAULT_LIMIT` = 50.

### 5.3 Ranking

**Architecture**: `CandidateScorer` protocol → `BaselineScorer` adapter → `RankTool`

| Scorer | Signal | Cold-start handling |
|--------|--------|---------------------|
| **Popularity** | Global item popularity (interaction count) | Works for all users |
| **ItemKNN** | Item-item collaborative filtering (cosine similarity) | Falls back to popularity |
| **BPR-MF** | Bayesian Personalized Ranking (matrix factorization) | Evaluation only (offline) |

**BaselineScorer** combines popularity (tiny weight 1e-6 for tie-breaking) + ItemKNN CF signal. Users with no CF signal get popularity only.

**RankTool output**: `ranked` (rank, item_id, score, domain), `model` name, `cold_start` flag, `excluded_seen`, `unscored_item_ids`, `has_personal_signal`, `note` (explanation if empty).

**Provenance**: `fit_provenance.py`, `file_hash.py`, `mapping_hash.py`, `fit_split_names.py` track artifact reproducibility.

**Evaluation metrics** (Layer 1 Outcome):
- `precision@k`, `recall@k`, `hit_rate@k`, `ndcg@k`, `mrr@k`, `map@k`
- `seen_item_rate`, `seed_in_result`, `distinct_domains`, `category_coverage`
- **Retrieval funnel**: `candidate_generation_count`, `retrieved_count`, `filtered_count`, `ranked_count`, `target_in_pool`, `target_reachable`, `stage_lost`

**Known limitation**: No embedding-based retrieval; BM25 recall on cold users unverified (data missing).

---

## 6. Agentic RAG Architecture

### 6.1 PlanExecutor (package/agents/planner/plan_executor.py)

**Core loop**: `plan()` → `run()` → optional `reflect()`

- **Planning**: One LLM call writes complete JSON plan (`steps[]`, optional `ask_user`). System prompt defines 6 tools with schemas.
- **Reference resolution**: `$N.path` (e.g., `$1.candidates`, `$2.ranked[0].item_id`). Resolved at execution time.
- **Invented ID check**: Before tool execution, args scanned for IDs not in user request or session history → rejected.
- **Execution**: Steps run sequentially. Tool errors captured per-step; failed step skips dependent steps.
- **Reflection triggers**:
  1. Step failed (tool error) and not invented ID / SQL timeout
  2. No items returned and not `ask_user`
  3. Quality threshold: `reflect_quality_threshold > 0` and pipeline quality < threshold
     - Quality: retrieval-only=0.5, ranking w/o CF=0.7, full pipeline w/ CF=1.0
- **Reflection rounds**: Up to `reflect_rounds` (config: 1). Failed reflection reply drops; previous result kept.
- **Output tracking**: `last_plan`, `last_question`, `last_response`, `last_usage`, `last_reflections`, `last_first_attempt_ok`, `last_attempt_plans`

### 6.2 Type1Agent (package/agents/type1/type1_agent.py)

**Fixed plan** (no LLM):
1. `SimilarTool` (retrieve candidates around seed items, `candidate_multiplier=5`, `min_candidates=50`)
2. `RankTool` (score candidates for user)
3. `LookupTool` (hydrate metadata for top-K)

Used for `similar`/`personalized` request kinds in agent evaluation.

### 6.3 Tools (6 controlled operations)

| Tool | Group | Input | Output (keys for `$N.path`) | Depends On | Planner? |
|------|-------|-------|------------------------------|------------|----------|
| `SearchTool` | Retrieval | `query` (English), `filters`, `limit` | `candidates` (w/ score), `total_matches`, `query_tokens`, `truncated`, `applied_filters` | Corpus (FTS5+BM25) | Yes |
| `FilterTool` | Retrieval | `filters`, `order_by`, `limit` | `candidates`, `total_matches`, `truncated`, `applied_filters` | Corpus | No |
| `SimilarTool` | Retrieval | `items` (seed), `top_k`, `domain`, `exclude_input` | `candidates` (item_id, similarity, domain), `unknown_items` | ItemKNN similarity | Yes |
| `RankTool` | Ranking | `user_id`, `candidates`, `top_k`, `exclude_seen` | `ranked`, `model`, `cold_start`, `excluded_seen`, `unscored_item_ids`, `has_personal_signal` | CandidateScorer | Yes |
| `LookupTool` | Hydration | `item_ids` OR `query` (SELECT), `max_rows` | `items`, `missing_item_ids`, `truncated` | Corpus | Yes |
| `MemoryTool` | Memory | `user_id`, `top_n_categories` | `user_id`, `known`, `n_interactions`, `top_categories`, `price_range`, `recent_items`, `love/hate_categories`, `loved/hated_items` | Interactions + Corpus | Only planner_memory |

**Retrieval → Ranking → Hydration**: Retrieval finds *which items might be relevant*; Ranking orders *which of these candidates are best*; Hydration fetches metadata for *known IDs*.

### 6.4 MemoryTool (package/memory/memory_tool.py)

**Read-only** — no write/update/forget (no dialogue to extract preferences from in Amazon Reviews 2023).

**Aggregates from interaction history + ItemCorpus** (SQL MIN/MAX/GROUP BY, not limited by `corpus.select` 100-row cap):
- `known` (False = cold start)
- `n_interactions`
- `top_categories` (most frequent)
- `price_range` (min/max)
- `recent_items` (most recent first, for SimilarTool seeds)
- `love_categories` / `hate_categories` (rating ≥ 4.0 / ≤ 2.0 by default)
- `loved_items` / `hated_items` (highest/lowest rated items)

**Leakage prevention**: `as_of_timestamp` parameter restricts to interactions ≤ timestamp (validated by `check_profile_snapshot`).

### 6.5 Inference Layer (package/inference/)

| Component | File | Purpose |
|-----------|------|---------|
| **compose_llm** | `compose/compose_llm.py` | LLM writes final answer from agent's `recommended` items. Validated by `check_grounding`. Retries up to `llm_retries`. |
| **compose_template** | `compose/compose_template.py` | Deterministic template fallback (no LLM call). |
| **grounding** | `grounding/check_grounding.py` | Checks: mentioned IDs ⊆ recommended IDs, bare ASINs, price/rating numbers within `price_tolerance`. Returns error string or None. |
| **Jev evaluation** | `evaluate_product_reply_with_jev.py` | LLM-as-judge: faithfulness (claim extraction + support check) + communication (relevance, clarity, language, honesty_about_gaps on 1-5 scale). |

**Inference modes** (from `inference.yaml`):
- `mode: llm` — LLM answer with grounding check + retry
- `mode: template` — Deterministic, no LLM

### 6.6 Multi-turn

**Status**: `package/evaluation/multi_turn/` has schemas, `conversations.jsonl` (11 scenarios M1–M7 + edge cases), evaluator, reporting, and a **real runner** (`_agent_runner.py`: PlanExecutor + Session + real LLM over fixture tools, wired in `_run.py`). `reference_correctness`/`context_retention` now return real measurements or `None` (not measurable) instead of placeholder 1.0. Requires `LLM_BASE_URL`/`LLM_API_KEY` — without them the CLI fails loudly.

---

## 7. End-to-End Data Flow (Example: Planner Agent)

```
User Request (Vietnamese)
    │
    ▼
[Optional] Translate to English keywords for SearchTool
    │
    ▼
PlanExecutor.plan() → LLM writes JSON plan
    │  Example: 
    │  { "steps": [
    │      {"tool": "MemoryTool", "args": {"user_id": "..."}},
    │      {"tool": "SearchTool", "args": {"query": "$1.top_categories[0] quiet keyboard", "filters": {"price_max": "$1.price_range.max"}}},
    │      {"tool": "RankTool", "args": {"user_id": "...", "candidates": "$2.candidates", "top_k": 10}},
    │      {"tool": "LookupTool", "args": {"item_ids": "$3.ranked[0:10].item_id"}}
    │  ]}
    │
    ▼
PlanExecutor.run() executes steps sequentially
    │
    ├─ Step 1: MemoryTool → user profile (top_categories, price_range, recent_items, ...)
    ├─ Step 2: SearchTool → BM25 candidates (resolves $1 references)
    ├─ Step 3: RankTool → ranked candidates (resolves $2.candidates)
    └─ Step 4: LookupTool → item metadata for top-K (resolves $3.ranked)
    │
    ▼
AgentOutcome: { recommended: [...], steps: [...], ask_user: null }
    │
    ▼
Inference.compose_answer() (LLM or template)
    │
    ▼
Grounding.check_grounding() validates answer against AgentOutcome.items
    │
    ▼
[Optional] Jev evaluation: faithfulness + communication quality
    │
    ▼
Final Response + Trajectory (saved to JSONL)
```

---

## 8. Evaluation Framework

### 8.1 Five-Layer Architecture (package/evaluation/)

| Layer | File | Focus | Key Metrics |
|-------|------|-------|-------------|
| **L1: Outcome** | `layer1_outcome/score_layer1_outcome.py` | Recommendation quality | precision@k, recall@k, hit_rate@k, ndcg@k, mrr@k, map@k, seen_item_rate, retrieval funnel |
| **L2: Interaction** | `layer2_interaction/score_layer2_interaction.py` | Output quality | task_success (v2, kind-specific), constraint_satisfaction, asked_clarification, exclusion_compliance |
| **L3: Grounding** | `layer3_grounding/score_layer3_grounding.py` | Faithfulness | answer_grounded, answer_fallback, retrieval diagnostics (target_in_pool, retrieved_by_*, stage_lost) |
| **L4: Process** | `layer4_process/score_layer4_process.py` | Planning quality | tool_selection_ok, argument_ok, plan_validity, reflection_triggered, reflection_rescued |
| **L5: Deployment** | `layer5_deployment/score_layer5_deployment.py` | Latency/cost | wall_seconds, token usage, provider_error_rate |

**Entry point**: `package/evaluation/trajectory/score_trajectory.py` orchestrates all 5 layers per trajectory.

### 8.2 Component Benchmarks (package/evaluation/component/)

**Component benchmarks** (`package/evaluation/component/benchmarks/`) — real tools where possible; quality gate (`pass`) is separate from execution `success`:

| Component | Dataset / Runner | Key Metrics | Status |
|-----------|------------------|-------------|--------|
| **Memory** | `memory_correctness_dataset.jsonl` (30 cases) + `memory_oracle.py` independent oracle | `all_fields_match_mean`, `future_leakage_max`, `success_rate` | ✅ Real MemoryTool vs oracle; thresholds configured (all_fields_match ≥ 0.95, success_rate = 1.0, leakage = 0) |
| **Planner** | `planner_dataset.jsonl` (32 cases) via `planner_benchmark.py` | tool_selection_accuracy, argument_correctness, plan_validity, constraint_handling, clarification_precision, refusal_to_guess | ⚠️ Real LLM + fixture corpus; requires `LLM_BASE_URL`/`LLM_API_KEY`; no thresholds yet |
| **Executor** | `executor_dataset.jsonl` (18 cases) via `executor_benchmark.py` | all_steps_ok, step_success_rate, error_kind_accuracy, reference_resolution_ok | ✅ Real tools over fixture corpus; measures `_execute` only (no plan/reflection — those need LLM, covered by planner benchmark + `tests/agents/test_executor_error_taxonomy.py`); no thresholds yet |
| **Grounding** | `grounding_dataset.jsonl` (32 cases) via `grounding_benchmark.py` | grounding_rate, hallucination_rate, prompt_injection_detected (heuristic), judge_error | ⚠️ Real Jev required (`TYPESAFE_API_KEY`); judged answer is real `compose_answer` output — `answer_mode=template` default (deterministic), `"llm"` via config (Phase 4.3); no thresholds yet |
| **Integration** | `integration_dataset.jsonl` (12 cases) via `integration_benchmark.py` | contract_valid, no_mismatch, grounded_rate | ✅ Real `_execute` → `outcome_from_plan_results` → `compose_answer` boundary — `answer_mode=template` default, `"llm"` via config (Phase 4.2); no thresholds yet |

**Unified runner**: `package/evaluation/component/_run_all.py` → subprocesses each component CLI → aggregates into `unified_report_*.json/.md`; exits non-zero if any component fails; shows per-component `pass`/`fail`/`not_evaluated` quality-gate status.

> **`no_mismatch` limitation (integration)**: the metric only compares `answer["items"]` ids against ids actually produced by executed tool steps. In both `template` and `llm` compose modes, `Answer.items` is copied from `outcome.items`, so the metric verifies the executor→adapter→composer provenance plumbing (it caught an injected foreign id in mutation testing) — it does **not** inspect ids mentioned in `answer["text"]`. Free-text hallucination checking belongs to `check_grounding`/Jev, not this metric. Similarly `grounded_rate` reflects the composer flag, which is `True` by construction in template mode.

### 8.3 Campaign Runner (package/evaluation/campaign/campaign_runner.py)

- Orchestrates multiple `run_agent_eval.py` experiments via subprocess
- Parameter grid expansion, comparison pairs (auto-generated pairs are actually consumed), repetition
- `campaign_id` is written into each experiment's `config.yaml` for provenance; non-metric keys (`n`, counts) excluded from comparison
- `statistical_settings` in campaign.yaml drives bootstrap CIs and paired delta CI/p-value in `_compare_experiments` (wired in Phase 4.1); `metadata` is still parsed but unused
- **Supports `--mock` flag** for testing without real data/LLM

### 8.4 Opik Integration Assessment

**Workstream A (Phases A0–A2)** — Complete (from previous branch):

| Phase | Deliverable | Key Finding |
|-------|-------------|-------------|
| A0 | `opik_phase_0_current_architecture.md` | RCM has 60+ custom metrics, flat trajectory format, no tracing framework |
| A1 | `opik_phase_1_capability_assessment.md` | Opik cannot replace RCM metrics; **recommends Option B: Complementary Integration** (Opik for tracing/UI, RCM for metrics) |
| A2 | `opik_phase_2_poc_report.md` | PoC demonstrated: load 58 trajectories, create Opik dataset, log metrics as metadata, custom metric wrapper pattern. Feasible, 1-2 weeks effort. |

**Status**: PoC only. No live Opik server deployed. No span instrumentation in RCM agents yet.

### 8.5 Configuration Centralization

**Workstream B (Phases B0–B3)** — Complete (from previous branch):

| Phase | Deliverable | Changes |
|-------|-------------|---------|
| B0 | `config_audit_inventory.md` | 48 findings: 8 MUST CENTRALIZE, 5 SHOULD, 20 KEEP AS CODE, 15 TEST-SPECIFIC |
| B1 | `config_architecture_design.md` | Design: reuse `load_config` with `CONFIG_OVERLAY_PATH`, add `src_root`/`config_dir` to `data_paths.yaml` |
| B2 | `config_centralization_phase_2_report.md` | Implemented: added `src_root`/`config_dir`, replaced path chains in 3 files, removed Jev timeout defaults from 2 files |
| B3 | `config_centralization_phase_3_verification.md` | Verified: Config tests 50 passed, Component tests 40 passed/2 skipped, Jev tests 8 passed, Path hygiene all passed |

**Result**: All operational parameters centralized in YAML. Single source of truth. Path resolution via `get_data_paths()`. No regression.

---

## 9. Configuration Architecture

### 9.1 Centralized Path Management (configs/path/data_paths.yaml)

**Single source of truth** for all directories:

```yaml
paths:
  src_root: "."
  config_dir: "configs"
  raw_dir: "resource/raw"
  cleaned_dir: "resource/cleaned"
  filtered_dir: "resource/filtered"
  mapped_dir: "resource/mapped"
  splits_dir: "resource/splits"
  item_knn_dir: "resource/item_knn"
  corpus_dir: "resource/corpus"
  log_dir: "experiments/logs"
  experiments_dir: "experiments"

outputs:  # Relative to experiments_dir
  baselines: "baselines"
  agent_eval: "agent_eval"
  candidate_recall: "candidate_recall"
  ranking_eval: "ranking_eval"
  ranking_diagnostics: "ranking_diagnostics"
  ablation: "agent_eval/ablation"
  component_benchmarks: "agent_eval/component_benchmarks"
  memory_utility: "agent_eval/memory_utility_analysis"
  multi_turn: "agent_eval/multi_turn"
  test_logs: "test_logs"
```

**Access in code**: `get_data_paths().corpus_path`, `get_data_paths().output_dir("agent_eval")`, etc.

### 9.2 Configuration Loading (package/config/load_config.py)

- `load_config("agent/llm")` → loads `configs/agent/llm.yaml` with Pydantic validation
- **Overlay support**: `CONFIG_OVERLAY_PATH` env var points to YAML that overrides base config (used by campaign runner)
- **Env var expansion**: `${VAR:-default}` syntax in YAML (e.g., `${LLM_BASE_URL:-}`)
- **Strict schemas**: `extra="forbid"` — unknown keys raise error
- **All scripts use `load_config`** — no direct `yaml.safe_load` (enforced by Jev reliability fix)

### 9.3 Key Config Files

| File | Purpose |
|------|---------|
| `configs/agent/agent.yaml` | PlanExecutor limits (max_steps, reflect_rounds, tokens, temperature) |
| `configs/agent/llm.yaml` | Provider, model, base_url, api_key, timeout |
| `configs/agent/agent_eval.yaml` | Agents list, request_scope, per_segment, trajectory_file |
| `configs/agent/inference.yaml` | Inference mode (llm/template), llm_retries, price_tolerance |
| `configs/eval/component_benchmarks.yaml` | Component benchmark runs, per-component configs |
| `configs/eval/judge.yaml` | Jev provider config (api_key, model, timeout, evaluation criteria) |
| `configs/evaluation/campaign.yaml` | Campaign orchestration (parameter_grid, comparison_pairs, repetition_count) |
| `configs/path/domains.yaml` | Domain list + `merged_name` (artifact tag for the all-domain merge, `multi_domain`) |

---

## 10. Scripts and Execution Workflows

### 10.1 Primary Entry Points

| Script | Purpose | Key Config |
|--------|---------|------------|
| `scripts/evaluation/run_agent_eval.py` | Full agent evaluation (ranking + agent metrics) | `agent_eval.yaml`, `agent.yaml`, `inference.yaml`, `eval/baselines.yaml` |
| `package/evaluation/component/run_benchmark_cli.py` | Single component benchmark | `component_benchmarks.yaml` (per-component config) |
| `package/evaluation/component/_run_all.py` | All 5 components + unified report | Same as above |
| `package/evaluation/campaign/campaign_runner.py` | Campaign orchestration | `evaluation/campaign.yaml` |
| `scripts/data_pipeline/run_pipeline.py` | Data pipeline (stages 1–4) | `data/cleaning.yaml`, `data/filtering.yaml`, `data/split.yaml`, `path/data_paths.yaml` |
| `scripts/evaluation/run_baselines.py` | Ranking baseline evaluation | `eval/baselines.yaml` |
| `scripts/demo/run_demo.py` | Gradio demo (mock/live) | `agent/demo.yaml` |
| `scripts/evaluation/opik_poc.py` | Opik complementary integration PoC | — |

### 10.2 Execution Conventions

- **All scripts require `PYTHONPATH=.`** (pytest sets via `pyproject.toml`; direct runs need explicit)
- **No CLI override flags** — all tunables in YAML (enforced by refactor)
- **Dataset tag derived from `--domain`**: `resolve_dataset_tag()` maps the domain selection to the artifact tag — one domain -> its name, all/none -> `merged_name` (`multi_domain`); other subsets are rejected. The tag controls `filtered_dir`, `mapped_dir`, `splits_dir`, `corpus_dir`, `item_knn_dir`, `log_dir`
- **Resume support**: `run_agent_eval.py --resume` continues from existing trajectory file
- **Mock mode**: `--mock` flag on `run_agent_eval.py`, `run_demo.py`, `run_campaign.py`, component CLI

---

## 11. Script Reference Details

### 11.1 Data Pipeline (Phase 3)

**`scripts/data_pipeline/run_pipeline.py`** — Run the full data pipeline or selected stages.

```bash
# Run all stages (1→2→3→4)
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py

# Run specific stages
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages 1
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages 1,2
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages 2,3,4

# Run for specific domains — exactly one domain or all (default); other subsets are rejected
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --domain Video_Games
# (all domains -> merged bundle 'multi_domain'; pass no --domain)

# Dataset tag derives from --domain: all domains -> 'multi_domain', one domain -> its name;
# other subsets are rejected (no --tag flag anymore)

# Force overwrite existing outputs
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --force

# Stage 1 options
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages 1 --domain Video_Games     --review-path /path/to/review_Video_Games.jsonl.gz

# Stage 2 options
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages 2 --cold-start-report

# Stage 4 options
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages 4     --skip-corpus     --skip-item-knn
```

**Stages**:
| Stage | Description |
|-------|-------------|
| 1 | Clean raw reviews per domain → `resource/cleaned/<domain>/interactions.parquet` |
| 2 | Merge domains + filter (k-core) → `resource/filtered/<tag>/interactions.parquet` |
| 3 | ID mapping + temporal split → `resource/mapped/<tag>/`, `resource/splits/<tag>/` |
| 4 | Build ItemCorpus SQLite + ItemKNN artifacts → `resource/corpus/<tag>/`, `resource/item_knn/<tag>/` |

### 11.2 EDA & Diagnostics

**`scripts/eda_diagnostic/run_eda.py`** — Streaming EDA on raw review files.

```bash
# All domains
PYTHONPATH=. python scripts/eda_diagnostic/run_eda.py

# Specific domain(s)
PYTHONPATH=. python scripts/eda_diagnostic/run_eda.py --domain Video_Games
PYTHONPATH=. python scripts/eda_diagnostic/run_eda.py --domain Video_Games --domain Toys_and_Games

# Direct file path
PYTHONPATH=. python scripts/eda_diagnostic/run_eda.py --path /path/to/review_Video_Games.jsonl.gz
```

**`scripts/eda_diagnostic/diagnose_splits.py`** — Check split quality (leakage, temporal order, user coverage).

```bash
PYTHONPATH=. python scripts/eda_diagnostic/diagnose_splits.py --domain Video_Games
```

### 11.3 Demo Scripts

**`scripts/demo/run_demo.py`** — Gradio UI demo.

```bash
# Mock mode (no data/LLM needed)
PYTHONPATH=. python scripts/demo/run_demo.py --mock

# Live mode with real data
PYTHONPATH=. python scripts/demo/run_demo.py --domain Video_Games

# Live mode options (inference mode, corpus flags, eval split come from
# configs/agent/demo.yaml and configs/agent/inference.yaml — not CLI)
PYTHONPATH=. python scripts/demo/run_demo.py     --domain Video_Games     --host 0.0.0.0     --port 7860
```

**Arguments**:
| Arg | Default | Description |
|-----|---------|-------------|
| `--mock` | false | Mock mode (no data/LLM needed) |
| `--domain` | all -> `multi_domain` | Domain(s) selecting the data bundle (repeatable; one domain or all only) |
| `--host` | 127.0.0.1 | Gradio host |
| `--port` | 7860 | Gradio port |

### 11.4 Tool Validation & Runner

**`scripts/tools/run_tools.py`** — Direct tool validation (no LLM, no agent). Validates tool logic with real data.

```bash
# List available tools
PYTHONPATH=. python scripts/tools/run_tools.py --list

# Run a single tool with JSON args
PYTHONPATH=. python scripts/tools/run_tools.py --tool SearchTool --args '{"query": "mechanical keyboard", "filters": {}, "limit": 5}'

# Chain tools
PYTHONPATH=. python scripts/tools/run_tools.py --chain SearchTool RankTool LookupTool --init-args '{"user_id": "user_123"}'

# Test data overrides
PYTHONPATH=. python scripts/tools/run_tools.py --tool MemoryTool --args '{"user_id": "u1"}' --interactions /path/to/interactions.parquet
```

**`scripts/tools/check_llm_provider.py`** — Quick LLM provider connectivity test.

```bash
PYTHONPATH=. python scripts/tools/check_llm_provider.py
```

### 11.5 Evaluation Scripts

**`scripts/evaluation/run_agent_eval.py`** — Full agent evaluation (ranking + agent metrics).

```bash
# Run on validation split
PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --eval-on validation

# Resume interrupted run
PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --resume

# Run on test split (use sparingly)
PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --eval-on test

# Mock mode (no data/LLM needed)
PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --eval-on validation --mock
```

**`scripts/evaluation/run_baselines.py`** — Ranking baseline evaluation (Popularity, ItemKNN, BPR-MF).

```bash
# Run on validation
PYTHONPATH=. python scripts/evaluation/run_baselines.py --eval-on validation

# With specific model
PYTHONPATH=. python scripts/evaluation/run_baselines.py --eval-on validation --model item_knn
```

**`scripts/evaluation/opik_poc.py`** — Opik complementary integration PoC.

```bash
PYTHONPATH=. python scripts/evaluation/opik_poc.py
```

### 11.6 Experiment Orchestration

**`scripts/experiments/compare_experiments.py`** — Compare experiment pairs (ablation).

```bash
PYTHONPATH=. python scripts/experiments/compare_experiments.py --contrast reflect_0_vs_reflect_1
```

**`scripts/evaluation/jev_smoke_test.py`** — Real Jev provider smoke test (manual, requires TYPESAFE_API_KEY).

```bash
TYPESAFE_API_KEY=your_key PYTHONPATH=. python scripts/evaluation/jev_smoke_test.py
```

### 11.7 Config Reference

All tunable parameters live in YAML. CLI flags are only operational selectors (`--domain`, `--eval-on`, `--resume`, `--work-dir`, `--candidates-from`, `--stages`, `--force`, `--mock`, `--host`, `--port`).

Key config files and their purposes:

| Config File | Purpose |
|-------------|---------|
| `agent/tools` | `configs/agent/tools.yaml` | Tool runtime limits (max steps, etc.) |
| `agent/agent` | `configs/agent/agent.yaml` | Agent limits (max steps, etc.) |
| `agent/agent_eval` | `configs/agent/agent_eval.yaml` | Agent eval settings |
| `eval/baselines` | `configs/eval/baselines.yaml` | Baseline model configs |
| `eval/tuning` | `configs/eval/tuning.yaml` | Hyperparameter grids |
| `eval/candidate_recall` | `configs/eval/candidate_recall.yaml` | Recall budgets |
| `eval/ranking_eval` | `configs/eval/ranking_eval.yaml` | Ranking eval settings |
| `eval/ranking_diagnostics` | `configs/eval/ranking_diagnostics.yaml` | Bottleneck analysis settings |
| `eval/tool_validation` | `configs/eval/tool_validation.yaml` | run_tools.py settings |
| `eval/memory_utility` | `configs/eval/memory_utility.yaml` | Memory utility analysis settings |
| `eval/component_benchmarks` | `configs/eval/component_benchmarks.yaml` | Component benchmark runs |
| `eval/recommendation_metrics` | `configs/eval/recommendation_metrics.yaml` | K values, metrics |
| `path/data_paths` | `configs/path/data_paths.yaml` | All filesystem paths |
| `path/domains` | `configs/path/domains.yaml` | Domain list + `merged_name` (derived artifact tag for all-domain runs) |

### 11.8 Output Locations

| Output | Location |
|--------|----------|
| Pipeline logs | `experiments/logs/<tag>/run_pipeline.log` |
| Tool validation log | `experiments/logs/<tag>/run_tools.log` |
| Baseline experiments | `experiments/baselines/exp_NNN/` |
| Agent eval experiments | `experiments/agent_eval/exp_NNN/` |
| Candidate recall experiments | `experiments/candidate_recall/exp_NNN/` |
| Ranking eval experiments | `experiments/ranking_eval/exp_NNN/` |
| Ranking diagnostics | `experiments/ranking_diagnostics/exp_NNN/` |
| Ablation comparisons | `experiments/agent_eval/ablation/` |
| Component benchmarks | `experiments/agent_eval/component_benchmarks/` |
| Memory utility analysis | `experiments/agent_eval/memory_utility_analysis/` |
| Multi-turn evaluation | `experiments/agent_eval/multi_turn/` |
| Test logs / results | `experiments/test_logs/` |

All of the above are configured in `outputs:` in `configs/path/data_paths.yaml` (relative to `experiments_dir`).

### 11.9 Common Patterns

```bash
# Always use PYTHONPATH=. from project root or cd src
cd /path/to/agentic-rag-for-rcm-sys
PYTHONPATH=. python src/scripts/...

# Or from src/
cd /path/to/agentic-rag-for-rcm-sys/src
python scripts/...

# Set domain for config interpolation
DOMAIN=Video_Games PYTHONPATH=. python scripts/...
```

### 11.10 Config Overlay (per-experiment overrides)

All tunables live in YAML; CLI flags are only operational selectors (`--domain`, `--eval-on`, `--resume`, `--work-dir`, `--candidates-from`, `--stages`, `--force`, `--mock`, `--host`, `--port`).

To run an experiment with different hyperparameters, write a YAML overlay shaped like the config tree and point `CONFIG_OVERLAY_PATH` at it:

```yaml
# overlay.yaml
agent/agent_eval:
  agent_eval:
    agents: [baseline, type1]
    per_segment: 2
agent/inference:
  inference:
    mode: template
```

```bash
CONFIG_OVERLAY_PATH=/path/to/overlay.yaml PYTHONPATH=.     python scripts/evaluation/run_agent_eval.py --eval-on validation
```

The campaign runner (`package/evaluation/campaign/`) writes one overlay per experiment automatically. Overlay fragments are deep-merged over the base configs before Pydantic validation, and changing the overlay invalidates cached limits.

---

## 12. Testing Strategy and Coverage

| Test Suite | Command | Coverage |
|------------|---------|----------|
| **Config tests** | `pytest tests/config/ -v` | 50+ passed (overlay, path resolution, schema validation) |
| **Corpus tests** | `pytest tests/corpus/ -v` | ItemCorpus build/load/save, FTS5 |
| **Data tests** | `pytest tests/data/ -v` | Pipeline stages, leakage checks, mapping |
| **Agent tests** | `pytest tests/agents/ -v` | PlanExecutor, Type1Agent, tools, session |
| **Recommender tests** | `pytest tests/recommenders/ -v` | Popularity, ItemKNN, BPR-MF |
| **Scoring tests** | `pytest tests/scoring/ -v` | BaselineScorer, CandidateScorer protocol |
| **Tool tests** | `pytest tests/tools/ -v` | All 6 tools, corpus, recommenders, scoring |
| **Evaluation tests** | `pytest tests/evaluation/ -v` | Component benchmarks, trajectory scoring, campaign |
| **Full suite** | `pytest tests/ -q` | 1395 passed, 0 skipped, 2 xfailed |

**Mock vs. Real Provider**:
- Component benchmarks: mixed — memory runs the **real** MemoryTool against an independent oracle; planner uses real LLM + fixture tools; grounding uses real Jev (`TYPESAFE_API_KEY`); executor runs real tools over the fixture corpus (`_execute` scope only); integration runs the real executor→inference boundary; grounding judges real `compose_answer` output; multi-turn has a real runner (`multi_turn/_agent_runner.py`, needs LLM creds)
- Agent evaluation: Can run with real LLM (requires `LLM_BASE_URL`, `LLM_API_KEY`)
- Jev smoke test: `scripts/evaluation/jev_smoke_test.py` for manual real-provider testing

---

## 13. Known Issues and Bottlenecks

### 13.1 Upstream Bottlenecks (Embedding → Retrieval → Ranking)

| Bottleneck | Evidence | Downstream Impact |
|------------|----------|-------------------|
| **No embedding retrieval** | `package/tools/embeddings/__init__.py`: "NOT IMPLEMENTED" | Cold users (72% single-interaction) rely on BM25 over English catalog; Vietnamese semantic gap |
| **BM25 recall unverified** | `candidate_recall` experiments exist but `resource/` data missing | If relevant items not retrieved, ranking cannot promote them |
| **ItemKNN similarity matrix** | Precomputed offline; cold items outside matrix → `unscored_item_ids` | Ranking falls back to popularity for unknown items |
| **Planner tool selection poor** | Low `tool_selection_accuracy` in component benchmark | Wrong tools → wrong candidates → poor ranking input |
| **Executor reflection ineffective** | `reflection_rescued=0.0` in component benchmark | Failed plans not corrected; quality threshold reflection untested |

**Dependency chain verified**: Embedding (absent) → Retrieval (BM25/FTS5) → Ranking (CandidateScorer) → Agent Tools → Agent Response → Grounding. Weak upstream quality propagates downstream.

### 13.2 Agentic Layer Issues

| Issue | Evidence | Status |
|-------|----------|--------|
| **Planner LLM produces invalid tool calls** | Low `tool_selection_accuracy` in component benchmark | Requires better prompt / few-shot / model |
| **Reflection doesn't rescue failures** | `reflection_rescued=0.0` in component benchmark | Quality threshold reflection (configurable) untested |
| **Grounding rate zero (old)** | Fixed in Phase 1 — missing Jev/key now FAILs instead of fake 1.0; Phase 4.3 judges real `compose_answer` output | Needs `TYPESAFE_API_KEY` for a real run |
| **Integration latency anomaly** | Low mean latency in component benchmark | Likely contract-only measurement |
| **Multi-turn not real-LLM evaluated** | Real runner implemented (Phase 4.4); needs LLM creds for an actual run | Run with credentials |

### 13.3 Evaluation Framework Gaps

| Gap | Evidence | Impact |
|-----|----------|--------|
| **No real-provider agent evaluation** | All component benchmarks mocked | Quality metrics from mocks ≠ real behavior |
| **Campaign runner unverified** | No data for real runs | Cannot run comparative experiments |
| **Retrieval recall unmeasured** | Environmental blocker | Cannot quantify upstream bottleneck |
| **Opik integration PoC only** | No live server, no span instrumentation | Tracing/observability not operational |
| **Provenance incomplete** | `git_sha` may be empty in reports | Cannot link results to exact code version |

### 13.4 Environmental Blockers

1. **`resource/` data missing** — Raw Amazon Reviews 2023 files, cleaned/filtered/mapped/splits, corpus, ItemKNN artifacts. Required for: agent evaluation, campaign runner, retrieval recall, baseline ranking.
2. **`LLM_BASE_URL` / `LLM_API_KEY` not set** — Required for planner benchmark and real agent evaluation.
3. **`TYPESAFE_API_KEY` not set** — Required for real Jev evaluation (grounding benchmark uses ScriptedJudge in CI).

---

## 14. Limitations and Unverified Areas

| Area | Status | Evidence |
|------|--------|----------|
| **Embedding-based retrieval** | Not implemented | Explicit in code |
| **Real LLM agent evaluation** | Not verified | Requires `LLM_BASE_URL` + `resource/` data |
| **Real Jev grounding evaluation** | Not verified | Requires `TYPESAFE_API_KEY` |
| **Campaign orchestration** | Code verified, artifacts empty | No real runs yet |
| **Retrieval recall (BM25 vs. embedding)** | Not measured | Phase 5: environmental blocker |
| **Vietnamese/English retrieval gap** | Not measured | Phase 5: environmental blocker |
| **Multi-turn real-LLM behavior** | Real runner exists; unverified without LLM credentials | Run `python -m package.evaluation.multi_turn._run` with creds |
| **BPR-MF online serving** | Evaluation only | `package/recommenders/evaluation/bpr_mf_recommender.py` |
| **End-to-end latency profiling** | Anomalous integration latency | Component benchmark shows contract-only measurement |
| **Provenance (git_sha, config hash)** | Partially implemented | `build_run_provenance.py` exists; `git_sha` may be empty |

---

## 15. Development Workflow

### 15.1 Running Tests
```bash
# Full suite (regression gate)
cd src && PYTHONPATH=. python -m pytest tests/ -q

# Specific suites
cd src && PYTHONPATH=. python -m pytest tests/config/ -v
cd src && PYTHONPATH=. python -m pytest tests/corpus/ -v
cd src && PYTHONPATH=. python -m pytest tests/evaluation/component/ -v
```

### 15.2 Running Component Benchmarks
```bash
# Single component (memory example; run count + config from configs/eval/component_benchmarks.yaml)
python -m package.evaluation.component.run --component memory --dataset package/evaluation/component/benchmarks/memory_correctness_dataset.jsonl

# All components + unified report
python -m package.evaluation.component._run_all
```

### 15.3 Running Agent Evaluation (requires `resource/` data + LLM)
```bash
PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --eval-on validation
PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --resume
PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --eval-on validation --mock  # Mock mode
```

### 15.4 Data Pipeline (requires raw data)
```bash
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages all --domain Video_Games --force
```

### 15.5 Configuration Override (for experiments)
```bash
CONFIG_OVERLAY_PATH=my_overlay.yaml PYTHONPATH=. python scripts/evaluation/run_agent_eval.py ...
```

---

## 16. Future Work and Recommended Investigation Order

### Priority 1: Resolve Environmental Blockers
1. **Obtain/generate `resource/` data** — Enables agent evaluation, campaign runner, retrieval recall, baselines
2. **Configure `LLM_BASE_URL` / `LLM_API_KEY`** — Enables planner benchmark, real agent evaluation
3. **Configure `TYPESAFE_API_KEY`** — Enables real Jev grounding evaluation

### Priority 2: Quantify Upstream Bottlenecks
4. **Measure BM25 recall** on real data (candidate_recall experiments)
5. **Evaluate embedding model candidates** (multilingual, Vietnamese+English) vs. BM25 baseline
6. **Analyze retrieval funnel** per request kind (similar vs. constrained vs. cold_text)

### Priority 3: Improve Agentic Quality
7. **Diagnose planner failures** — Low tool_selection_accuracy: prompt engineering, few-shot examples, model upgrade
8. **Fix reflection effectiveness** — Quality threshold reflection untested; `reflect_quality_threshold` in config
9. **Validate grounding with real answers** — Dummy answer limitation fixed; test with real LLM inference output

### Priority 4: Operationalize Evaluation
10. **Complete Opik complementary integration** — Deploy Opik, add `@opik.track` decorators, import historical experiments
11. **Fix integration latency measurement** — Ensure end-to-end execution time captured
12. **Populate `git_sha` in all reports** — Link results to exact code version
13. **Add real-provider smoke tests** to CI (optional, gated)

### Priority 5: Architectural Enhancements
14. **Implement embedding-based retrieval** if BM25 recall insufficient
15. **Add BPR-MF to online serving** (currently evaluation only)
16. ~~Real multi-turn evaluation~~ — done in Phase 4.4 (`_agent_runner.py`); pending a credentialed run
17. **Cross-domain recommendation** (currently per-domain corpus)

---

## 17. Glossary of Important Components and Terms

| Term | Definition |
|------|------------|
| **ItemCorpus** | Read-only SQLite database (FTS5 + BM25) storing item metadata. Built once, locked with `PRAGMA query_only=ON` and authoriser. |
| **CandidateScorer** | Protocol for scoring candidate items for a user. Implemented by `BaselineScorer` (popularity + ItemKNN). |
| **PlanExecutor** | LLM-based agent: writes JSON plan → executes steps → optional reflection. Main planner agent. |
| **Type1Agent** | Fixed-plan agent (no LLM): retrieve → rank → fetch. Used for baseline comparisons. |
| **$N.path** | Reference syntax in planner: `$1.candidates`, `$2.ranked[0].item_id`, etc. Resolved at execution. |
| **MemoryTool** | Read-only user profile from interaction history (categories, price range, love/hate, recent items). |
| **Jev (TypeSafe AI)** | LLM-as-judge service for faithfulness (claim support) and communication quality (1-5 scale). |
| **Grounding** | Validation that answer only mentions items from `recommended` list, with correct numbers. |
| **Retrieval Funnel** | S0(target in pool)→S1(candidate gen)→S2(retrieval)→S3(filtering)→S4(ranking)→S5(final inclusion). |
| **Oracle Request Kinds** | `constrained`, `cold_text` — use held-out target categories/prices. Upper bound, not real queries. |
| **CONFIG_OVERLAY_PATH** | Env var for per-experiment config overrides (used by campaign runner). |
| **Dataset Tag** | Artifact-directory identifier derived from `--domain` via `resolve_dataset_tag()` (one domain -> its name, all -> `merged_name` = `multi_domain`); stored as `tag` in provenance/manifests. |
| **Provenance** | Artifact tracking: file_hash, mapping_hash, fit_provenance, git_sha, config hash. |
| **ScriptedLLM** | Test double in `package/evaluation/doubles/`: returns pre-scripted responses for testing. |
| **ScriptedJudge** | Test double in `package/evaluation/doubles/`: returns pre-scripted Jev-like judgments. |
| **Fake*Tool** | Test doubles in `package/evaluation/doubles/`: deterministic fake tools for benchmarks. |

---

## 18. Evaluation Framework Reference (consolidated)

> This section merges the still-valid content of the former per-topic docs
> (`package/evaluation/{ARCHITECTURE,CAMPAIGN,EXECUTION,METRICS,MULTI_TURN,REQUEST_KINDS,FINAL_SUMMARY}.md`,
> `campaign/README.md`, `component/README.md`, `benchmarks/planner_README.md`,
> `benchmarks/README.md`, `scripts/README.md`, `tests/README.md`, `tests/tools/README.md`),
> which were removed in Phase 3 repository hygiene. Corrections applied:
> `run_all.py` → `_run_all.py`; multi-turn marked not-implemented; executor status updated.

### 18.1 Package Layout (`package/evaluation/`)

```
package/evaluation/
├── _schema.py / _loader.py / _evaluator.py / _regression.py   # core trajectory eval
├── trajectory/        # score_trajectory.py orchestrates L1–L5 per trajectory
├── layer1_outcome/ … layer5_deployment/                       # the five layers (§8.1)
├── recommender/       # recommender (ranking) evaluation: core, metrics, experiment, config
├── component/         # component benchmarks (§8.2)
│   ├── _schema.py / _evaluator.py / _loader.py / _regression.py / run.py / _run_all.py / run_benchmark_cli.py
│   └── benchmarks/    # planner/grounding/integration/memory datasets + evaluators, fixtures/
├── campaign/          # CampaignConfig, CampaignRunner, CheckpointManager, example_campaign.yaml
├── multi_turn/        # schemas + conversations.jsonl (11 scenarios) — NOT IMPLEMENTED runner (§6.6)
├── statistics/        # bootstrap.py: CIs, paired bootstrap, Wilcoxon, Mann-Whitney
├── reporting/         # generator.py (Markdown/CSV/failure reports); visualizations.py = placeholders
├── ablation/          # ablation experiment loading/statistics
├── product_reply/     # evaluate_product_reply_with_jev.py (Jev faithfulness + communication)
├── doubles/           # test doubles: Fake*Tool, ScriptedLLM, ScriptedJudge (tests/benchmarks only)
└── provenance/        # build_run_provenance.py
```

### 18.2 Seven Request Kinds

`similar`, `personalized`, `constrained`, `cold_text`, `ambiguous`, `exclusion`, `unanswerable`.
Each has kind-specific success criteria — do not force identical scoring:
- **similar**: leverage seed items via similarity search (ItemCF/semantic)
- **personalized**: use MemoryTool profile; respect loved/hated items and price range
- **constrained**: every filter correctly applied; no violating items
- **cold_text**: semantic/lexical match to text; no hallucinated items
- **ambiguous**: ask clarification rather than guess; process clarified request after
- **exclusion**: excluded items/categories absent; persist across turns
- **unanswerable**: recognize impossibility/out-of-domain; explain, don't fabricate

### 18.3 Metrics Summary (L1–L5)

- **L1 Recommendation quality**: precision@k, recall@k, hit_rate@k, ndcg@k, mrr@k, map@k, seen_item_rate, seed_in_result, distinct_domains, category_coverage; retrieval funnel (candidate_generation → retrieved → filtered → ranked → target_in_pool/reachable/stage_lost)
- **L2 Task success**: task_success (kind-specific v2), constraint_satisfaction, price_unknown_rate, asked_clarification, grounded-answer condition, love_alignment, hate_violation_rate, exclusion_compliance
- **L3 Retrieval & grounding**: target availability, retrieved-by-stage S0–S5, query-hit tokens, rank_in_pool, answer_grounded
- **L4 Planning & execution**: plan_validity, planning_attempts, truncation, step_count, step_success_rate, reflection_count, first_attempt_ok, tool_selection, argument_validity, ranker_usage
- **L5 Efficiency & cost**: prompt/completion tokens, llm/tool/wall latency, cost per request & per successful request, provider_error_rate

Component-level: execution reliability (ran without error) is tracked separately from functional correctness metrics. Quality gates: `thresholds` per component in `configs/eval/component_benchmarks.yaml` → `pass`/`fail`/`missing` per metric; overall `pass: true|false|null` (`null` = `not_evaluated`).

Metric formulas (from former METRICS.md):

- **L1**: precision@k = |rec ∩ rel| / |rec|; recall@k = |rec ∩ rel| / |rel|; hit_rate@k = 1 if any relevant in top-k; ndcg@k = DCG/IDCG with DCG = Σ(2^rel − 1)/log2(i+1); mrr@k = 1/rank(first relevant); map@k = mean AP@k; seen_item_rate = |rec ∩ history| / |rec|; seed_in_result = binary; distinct_domains = count
- **L2**: task_success = binary all-constraints; constraint_satisfaction = |satisfied| / |required|; price_unknown_rate = |unknown price| / |total|; love_alignment = |rec ∩ loved| / |rec|; hate_violation_rate = |rec ∩ hated| / |rec|; exclusion_compliance = binary
- **L3**: target_in_pool / retrieved_by_stage_Si = binary per stage; query_hit_any_title_token = binary; rank_in_pool = position
- **L4**: plan_validity / truncation / first_attempt_ok = binary; planning_attempts / step_count / reflection_count = counts; step_success_rate = |ok steps| / |steps|; tool_selection = |correct| / |total|; argument_validity = |valid| / |total|
- **L5**: prompt/completion tokens, llm/tool/wall latency = sums; cost_per_request = token_cost / requests; cost_per_successful_request = token_cost / successes; provider_error_rate = errors / calls
- **Component**: execution_reliability = |successful executions| / |total executions|
- **Multi-turn** (schema only, runner not implemented): turn_success_rate = |ok turns| / |turns|; conversation_success = all turns ok; item_match_rate = |expected ∩ actual| / |expected|; context_retention = shown_items grows monotonically; reference_accuracy = mean reference_correctness

Multi-turn metrics (schema exists, runner not implemented): turn_success, item_match_rate, exclusion_compliance, reference_correctness; conversation-level turn_success_rate, conversation_success, avg_item_match_rate, context_retention, reference_accuracy. Conversation succeeds only if all turns succeed.

### 18.4 Component Benchmark Framework

- Datasets: JSON/JSONL `BenchmarkCase` (`case_id`, `input`, `expected`, `tags`, `metadata` with `difficulty`/`tier`)
- `ComponentEvaluator` base: `run_component()` + `score_component()`; `success` = execution reliability, `metrics` = correctness; `thresholds_result` added Phase 2.1
- Run count + per-component config in `configs/eval/component_benchmarks.yaml`; outputs under `data_paths.outputs.component_benchmarks`
- CLI: `python -m package.evaluation.component.run --component <name> --dataset <path> [--tags …] [--metadata k=v …] [--git-sha …]`; regression: `… run regress --baseline … --candidate …`
- Unified: `python -m package.evaluation.component._run_all` → `unified_report_*.json/.md`, non-zero exit on any failure
- Memory correctness is verified against an **independent oracle** (`memory_oracle.py`), not the implementation under test; committed dataset must match oracle output (sync test)
- Planner benchmark uses real LLM + fixture corpus (`fixtures/create_test_*`); fails fast without LLM credentials; real LLM output is non-deterministic

### 18.5 Campaign Framework

Two config styles (both supported by `CampaignConfig`):
- **`parameter_grid`**: Cartesian product auto-generates experiments; `agents`/`inference_mode`/`reflect_rounds` → `agent_config`, `per_segment` → `evaluation_config`; empty `comparison_pairs` auto-fills as all-vs-first (baseline)
- **`experiments`**: explicit list with `agent_config`, `evaluation_config`, `repetition_count`, `random_seed`, `tags`

Runtime: `scripts/evaluation/run_campaign.py --campaign-config <yaml> [--dry-run] [--git-sha …]`. Each experiment writes `config_overlay.yaml` (applied via `CONFIG_OVERLAY_PATH` to `run_agent_eval.py`); overlay path/sha256 recorded in provenance. Unknown keys in `agent_config`/`evaluation_config` are **rejected**.

Result: `campaign_result.json` with `runs[]` (metrics, duration, success), `comparisons{}` (deltas: a, b, delta, relative_delta), `summary{}` (success rate, per-experiment stats), timestamp + git_sha. Checkpoint/resume via `campaign_checkpoint.json`. Comparisons currently compute plain deltas only — `statistical_settings` (confidence_level, bootstrap_samples, paired_comparison) is defined but **not yet consumed** (Phase 4.1).

Note: `campaign.yaml` under `configs/` loads via `load_config` (`CampaignConfig.from_yaml` routes configs/-relative paths) — env interpolation, `extra="forbid"` schema (`CampaignFileConfig`) and `CONFIG_OVERLAY_PATH` overlay all apply; paths outside `configs/` still read raw.

### 18.6 Execution, Resume, Compare, Export

- Component benchmarks: re-run with same config; results in timestamped JSON; regression via `compare_benchmarks`
- Campaigns: `CheckpointManager.save_checkpoint/load_checkpoint`; completed experiments skipped on resume
- Reports (`package/evaluation/reporting/`): `generate_markdown_report`, `generate_csv_export`, `generate_failure_report`, `generate_comparison_report`, `generate_all_charts` — **charts are text placeholders only** (no matplotlib/plotly)
- Statistics (`package/evaluation/statistics/`): bootstrap CI (mean/CI via percentile), `paired_bootstrap_difference` (mean diff, CI, p-value), `significance_test` (Wilcoxon signed-rank paired / Mann-Whitney U independent, alpha=0.05), aggregation (mean/std/min/max/P50/P95/P99)
- Provenance per run: git SHA, source fingerprint, env versions, hardware, timestamp, seed, dataset version

### 18.7 Scripts & Tests Layout (condensed)

- `scripts/data_pipeline/run_pipeline.py` — stages 1–4 (clean → merge/filter → map/split → corpus+ItemKNN)
- `scripts/eda_diagnostic/` — `run_eda.py`, `diagnose_splits.py`
- `scripts/demo/` — `run_demo.py` (Gradio; `--mock`), `demo_full_agent.py`
- `scripts/evaluation/` — `run_agent_eval.py`, `candidate_recall.py`, `run_campaign.py`, `opik_poc.py`, `jev_smoke_test.py`, `evaluate_product_reply.py`
- `scripts/tools/` — `run_tools.py`, `check_llm_provider.py`
- `scripts/llm_agent/smoke_real_llm.py`, `scripts/experiments/compare_experiments.py`
- `benchmarks/` — `run_baselines.py`, `tune_baselines.py`
- Tests: unit (mocked deps), integration (`@pytest.mark.integration`), real smoke tests are scripts not pytest; `tests/tools/` uses the "tiny world" fixture from its `conftest.py`; `tests/tools_helpers.py` provides `corpus`/`cf_setup` fixtures for hardening/regression tests

### 18.8 Known Framework Limitations (carried forward)

- Charts/visualizations are placeholders; `generate_example_report.py` uses synthetic data and is not wired into any pipeline
- Multi-turn real-LLM run still needs credentials (runner implemented in Phase 4.4)
- Planner/grounding/multi-turn benchmarks need LLM/Jev credentials for a real run
- `no_mismatch` (integration) verifies `answer["items"]` provenance only — not free-text ids in `answer["text"]` (that is `check_grounding`/Jev)
- Bootstrap with 1000 samples may be slow on large datasets
- Non-parametric tests assume non-normal data; no automatic normality check

---

## 19b. Benchmark audit notes (Phase 6, branch `audit/benchmark-quality`)

- **Grounding / Jev evidence fields**: `evaluate_product_reply_with_jev` now receives
  all `ITEM_FIELDS` (previously only `item_id`, `title`, `main_category`, `price`).
  Claims about `store`, `average_rating`, `rating_number`, `domain` are now
  judge-verifiable. The earlier real-Jev run (`grounding_rate_mean=0.906`,
  artifact `grounding_benchmark_20261108_165543.json`) is **not comparable** to
  post-change runs — the judge saw strictly less evidence before.
- **Template mode is a smoke test only**: `compose_answer(mode="template")`
  prints evidence fields verbatim and cannot hallucinate; benchmark output
  reports `measurement_scope = "does not measure hallucination
  (answer_mode=template)"`. Hallucination requires `mode="llm"`.
- `label_agreement` compares Jev-derived metrics against hand-authored
  `expected` labels; `total_claims` is reported but intentionally not
  assertable (produced by `_extract_claims` inside the measured pipeline).
- Judge-level negative control:
  `src/scripts/evaluation/jev_negative_control.py` (manual, needs `TYPESAFE_API_KEY`).

---

## 19. Document Provenance

| Field | Value |
|-------|-------|
| **Document** | `src/repo reading.md` (renamed from `Project repository reading 29.10.md` per D2; consolidated evaluation docs in §18) |
| **Update date** | 2026-11-09 |
| **Branch** | `tools-building` |
| **Commit** | `0ce2ea8` ("Phase 2.1: quality gate thresholds + verification fixes") |
| **Working tree** | Clean except untracked `experiments/` artifacts |
| **Key evidence sources** | Week 46 audit (`docs/audit_week46_report.md`), phase reports (`docs/phase1_report.md`, `docs/phase2_report.md`), source code inspection, GitNexus index |
| **Unresolved evidence** | `resource/` data (missing), real LLM/Jev evaluation (no credentials), multi-turn real run (needs LLM creds) |

---

**End of Repository Reading**
