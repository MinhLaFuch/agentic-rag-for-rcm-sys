---
created: 2026-09-27-15:07
updated: 2026-11-14-14:00
viewed: 2026-11-14-14:00
branch: tools-building
commit: 880bf5c
---
> **NOTE (2026-11-15):** This is a dated snapshot. The current central document is `src/reading.md` — it supersedes this file and includes the evaluation-integrity fixes (R1–R3, items 23–25).

**agentic-rag-for-rcm-sys / src** — An LLM-agent product recommender running on Amazon Reviews 2023 (3 domains: Video_Games, Toys_and_Games, Electronics).

> **Architectural principle:** The LLM only decides *what to do*; tools provide controlled operations; ItemCorpus provides item knowledge; recommenders provide recommendation signals; the agent layer combines results; the inference layer writes the final response using only items the agent selected.

## 0.1. Repository State (as of 2026-11-14)

| Item | Value |
|------|-------|
| **Repository root** | `C:\\Users\\ph181\\Documents\\Repositories\\agentic-rag-for-rcm-sys` |
| **Current branch** | `tools-building` (evidence: `git rev-parse --abbrev-ref HEAD` → `tools-building`) |
| **HEAD commit** | `880bf5c` ("0749_1110") (evidence: `git log --oneline -1` → `880bf5c 0749_1110`) |
| **Working tree** | Large uncommitted evaluation work: ~40 modified + ~70 untracked entries (evidence: `git status --short` → 112 lines; see §0.1.3) |
| **GitNexus index** | Updated with current structure |
| **Test baseline** | 1696 tests collected (evidence: `python -m pytest --collect-only -q` → `1696 tests collected in 3.07s`) |

### 0.1.1. Key Changes from Previous Version (refactor-phase-0 branch)

| Change Area | Before (refactor-phase-0) | After (tools-building) |
|-------------|---------------------------|------------------------|
| **Package structure** | `package/{corpus,recommenders,tools/{scoring,sql,ranking,retrieval,base}}` | `package/{corpus,recommenders,tools/{scoring,sql,ranking,retrieval,base},utils}` + `package/evaluation/` expanded |
| **Tools** | 6 tools distributed: `corpus/`, `recommenders/`, `tools/{scoring,sql,ranking,retrieval,base}` | 6 tools in `package/tools/{retrieval,ranking,scoring,sql,base}` + `package/utils/` |
| **Recommendation evaluation** | `package/evaluation/recommender/` (core, metrics, experiment, config, utils) | `package/evaluation/recommender/` + campaign orchestration |
| **Agent evaluation** | `package/evaluation/` + `trajectory/`, `product_reply/`, `doubles/`, `recommender/` | Expanded with campaign runner, multi-turn, component benchmarks |
| **Mock vs Real** | Merged with `--mock` flag, `package/evaluation/doubles/` for test doubles | Same, with Jev/OpenRouter integration for real LLM eval |
| **Component benchmarks** | 5 components: Memory, Planner, Grounding, Integration, Executor | 5 components maintained; campaign integration added |
| **Tests** | 368 passed, 4 skipped, 6 warnings | **1696 collected** (evidence: pytest collect output) |

### 0.1.2. Refactor Summary (Phases 0-10.1 Complete)

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
| 9 | Campaign orchestration & experiment pinning | ✅ Complete (evidence: git log `12b287e Pin campaign experiment artifacts`, `eb0a449 Fit ItemKNN once per campaign`) |
| 10 | Jev/OpenRouter integration & multi-turn eval | ✅ Complete (evidence: git log `18d33a2 Rename judge env vars`, `708149b Allow judge config to route Jev`, `987880f Opt every grid experiment into multi-turn eval`) |
| 10.1 | Record execution log - all 7 steps complete, Baseline B maintained | ✅ Complete (evidence: git log `880bf5c 0749_1110`) |

**Overall:** Refactor complete through Phase 10.1. Phase E (MockAgentRunner replacement) skipped as optional. Current branch `tools-building` includes campaign orchestration, Jev/OpenRouter judge integration, multi-turn evaluation opt-in, and ItemKNN cache reuse.

### 0.1.3. Recent Evaluation Work Log (2026-11-13 → 2026-11-14, uncommitted)

All changes below are **uncommitted** on `tools-building` @ `880bf5c`. Detailed docs: `src/docs/investigation_week47.md`, `src/docs/case_proposal_week47.md`, `src/docs/eval_surface_inventory.md`, `src/docs/ablation_scope.md`.

| Area | Change | Evidence |
|------|--------|----------|
| **Campaign resume** | `run_campaign.py --only 7,8,11,12` subset selection; per-experiment timeout 3600→7200s; merge keeps skipped runs and **recomputes comparisons+ablation over merged runs** (2026-11-16 — preserves consistency after re-running a timed-out exp); trajectory-level `--resume` per `{campaign_id}_{exp}_run{N}_trajectories.jsonl`; `git_sha` recorded | `campaign.yaml`, `campaign_runner.py`, `run_campaign.py`, `test_only_subset.py`; campaign_001 = 12/12 successful |
| **Benchmark cases** | +5 executor cases (exec_019–023), +3 planner cases (planner_033–035), +1 integration case (int_013); `expect_*` metrics; `resolved_config`/limits plumbing | `executor_dataset.jsonl` (22), `planner_dataset.jsonl` (29), `integration_dataset.jsonl` (13) |
| **Multi-turn eval** | Repaired per-turn metrics (expect_* handling, resolved_config); +2 negative conversations → `conversations.jsonl` = 13 | `multi_turn/_schema.py`, `_agent_runner.py`, `_eval_step.py`, `_run.py`, `multi_turn_evaluator.py` |
| **Source fingerprint** | `_source_fingerprint()` now hashes `pyproject.toml` + all `.py/.yaml/.yml` under `src/{package,scripts,configs}` (was repo-root only → blind to code drift). **Consequence:** old trajectories/artifacts won't resume under changed code (intentional provenance) | `recommender/experiment/save_experiment.py`; `test_source_fingerprint.py` (4 tests) |
| **Demo sessions** | `LiveBackend._sessions` bounded LRU: `DemoLimits.max_sessions` (default 100, `configs/agent/demo.yaml`), `DemoConfig.max_sessions` schema field; session-attach moved inside try/finally (latent session-bleed hardening) | `demo/_limits.py`, `demo/backend/live_backend.py`, `config/_schemas.py`; `tests/demo/test_live_backend_session.py` |
| **Tool subsets** | `AgentTools.for_planner/for_planner_memory(exclude_tools=...)` + `validate_tool_names()`; `agent_eval.exclude_tools` config key plumbed through `run_agent_eval.py` + campaign overlays → provenance | `agents/toolkit/agent_tools.py`, `run_agent_eval.py`, `campaign_runner.py` |
| **Ablation** | `ablation.yaml` rewritten with real campaign_001 run dirs + clean contrasts; new pairwise analysis (`_pairwise.py`, `pairwise_ablation.py`): McNemar, bootstrap CI, Wilson intervals, None-aware effective n; `campaign_ablation_norank.yaml` arm config (−RankTool) | `evaluation/ablation/_pairwise.py`, `_statistics.py`; `docs/ablation_scope.md` |
| **Component runner** | Grounding preflight: `skipped_no_credentials` when no Jev/TypeSafe/OpenRouter key (was hard error); `backlog_datasets` + `run_backlog` flag wire `planner_dataset_backlog.jsonl` (6 cases) as opt-in capability tracking, `skipped_backlog` by default | `component/_run_all.py`, `configs/eval/component_benchmarks.yaml`; `test_run_all.py` |
| **Eval inventory** | New doc mapping which eval surfaces run inside vs outside campaign_001 | `docs/eval_surface_inventory.md` |

**Pending (needs LLM credentials):** planner baseline benchmark → planner fixes; `-RankTool` campaign arm → final ablation numbers; Phase-7 summary after those runs.

## 0.2. Repository Structure

```
src/
├── configs/                              # YAML configuration (single source of truth)
│   ├── agent/                            # agent.yaml, llm.yaml, agent_eval.yaml, inference.yaml, ...
│   ├── data/                             # cleaning.yaml, filtering.yaml, split.yaml
│   ├── eval/                             # component_benchmarks.yaml, judge.yaml, baselines.yaml, ...
│   ├── evaluation/                       # campaign.yaml
│   └── path/                             # data_paths.yaml (centralized paths), domains.yaml, run_tag.yaml
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
│   │   ├── campaign/                     # Campaign orchestration (evidence: `src/package/evaluation/campaign/`)
│   │   ├── component/                    # Component benchmarks (Memory, Planner, Grounding, Integration, Executor)
│   │   ├── layer1_outcome/               # Layer 1: Recommendation quality
│   │   ├── layer2_interaction/           # Layer 2: Output quality
│   │   ├── layer3_grounding/             # Layer 3: Faithfulness
│   │   ├── layer4_process/               # Layer 4: Planning quality
│   │   ├── layer5_deployment/            # Layer 5: Latency/cost
│   │   ├── ablation/                     # Ablation experiments
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
│   │   └── sql/                          # FilterTool, LookupTool
│   └── utils/                            # Utilities (evidence: `src/package/utils/` exists; `src/package/tools/utils/` does NOT exist)
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

**Directory structure corrections (evidence-based):**
- `campaign/` appears **once** under `package/evaluation/campaign/` (and once under `tests/evaluation/campaign/` for tests) — previous version showed duplicate under `package/evaluation/`
- `tools/utils/` **does not exist** (evidence: `Get-ChildItem -Recurse -Directory -Filter "utils"` shows no `tools/utils` under package)
- `utils/` exists at `package/utils/` and `package/evaluation/recommender/utils/` (evidence: same command output)---

## 0.3. Agentic RAG Architecture (Updated)

### 0.3.1. PlanExecutor

**File**: `package/agents/planner/plan_executor.py` [[evidence: plan_executor.py lines 1-52]]

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

### 0.3.2. Type1Agent

**File**: `package/agents/type1/type1_agent.py` [[evidence: type1_agent.py lines 1-22, 25-70]]

**Fixed plan** (no LLM):
1. `SimilarTool` (retrieve candidates around seed items, `candidate_multiplier=5`, `min_candidates=50`)
2. `RankTool` (score candidates for user)
3. `LookupTool` (hydrate metadata for top-K)

Used for `similar`/`personalized` request kinds in agent evaluation.

### 0.3.3. Agent Types (vs `configs/agent/agent_eval.yaml`)

| Agent | Planning | LLM | Tools | Use Case |
|-------|----------|-----|-------|----------|
| **baseline** (ItemKNN) | Fixed (retrieve→rank→fetch) | No | SimilarTool, RankTool, LookupTool | Pure CF, no LLM cost |
| **type1** | Fixed (retrieve→rank→fetch) | No | SearchTool, RankTool, LookupTool | Text query → retrieval → ranking |
| **planner** | LLM-generated JSON plan | Yes | SearchTool, FilterTool, SimilarTool, RankTool, LookupTool | Complex multi-step reasoning |
| **planner_memory** | LLM-generated JSON plan | Yes | All 6 tools (SearchTool, FilterTool, SimilarTool, RankTool, LookupTool, MemoryTool) | Personalized with user profile |

> **Evidence**: `configs/agent/agent_eval.yaml` lines 5-10 defines `agents: [baseline, type1, planner, planner_memory]` with comments describing each. The tool sets for planner/planner_memory derived from `agent_tools.py` `for_planner()` and `for_planner_memory()` [[evidence: agent_tools.py lines 22-26]].---

## 0.4. Pipeline Overview

The end-to-end pipeline consists of a **data pipeline** (4 stages), a **component benchmark layer** (6 components), and an **agent evaluation layer** (5-layer framework + campaign orchestration).

### 0.4.1. Data Pipeline (scripts/data_pipeline/run_pipeline.py — 4 Stages)

| Stage | Script | Input | Output | Key Config |
|-------|--------|-------|--------|------------|
| 1 | `clean_domain()` | `resource/raw/<Domain>.jsonl.gz` | `resource/cleaned/<Domain>/interactions.parquet` | `data/cleaning.yaml` |
| 2 | `merge_filter_domains()` | `resource/cleaned/` | `resource/filtered/<tag>/interactions.parquet` | `data/filtering.yaml` |
| 3 | `map_split()` | `resource/filtered/<tag>/interactions.parquet` | `resource/mapped/<tag>/{user2id,item2id}.json`, `resource/splits/<tag>/{train,validation,test}.parquet` | `data/split.yaml` |
| 4 | `build_artifacts()` | `resource/mapped/`, `resource/splits/`, `resource/raw/meta_<Domain>.jsonl.gz` | `resource/corpus/<tag>/corpus_<tag>.sqlite`, `resource/item_knn/<tag>/item_knn_<tag>_<eval_on>.npz` | `data/split.yaml` (item_knn_splits) |

**Run**: `PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py [--stages 1,2,3,4] [--domain Video_Games] [--force] [--cold-start-report] [--skip-corpus] [--skip-item-knn]`

### 0.4.2. Component Benchmarks (package/evaluation/component/ — 6 Components)

**Unified runner**: `package/evaluation/component/_run_all.py` → subprocesses each component CLI → aggregates into `unified_report_*.json/.md` in `experiments/agent_eval/component_benchmarks/`.

| Component | Dataset (configs/eval/component_benchmarks.yaml) | Key Metrics | Status |
|-----------|--------------------------------------------------|-------------|--------|
| **Memory** | `memory_correctness_dataset.jsonl` (29 cases) | `known_correct`, `n_interactions_correct`, `top_categories_exact`, `loved_items_exact`, `all_fields_match`, `future_leakage` | ✅ Works (mock tools) |
| **Planner** | `planner_dataset.jsonl` (29 cases, incl. planner_033–035) | `tool_selection_accuracy`, `argument_correctness`, `plan_validity`, `constraint_handling`, `clarification_precision`, `refusal_to_guess` | ✅ Implemented (requires LLM) |
| **Executor** | `executor_dataset.jsonl` (22 cases, incl. exec_019–023) | `all_steps_ok`, `reflection_rescued`, `reflection_triggered` | ✅ Implemented (mock LLM + controlled tools) |
| **Grounding** | `grounding_dataset.jsonl` (35 cases) | `claims_supported`, `grounding_rate`, `hallucination_rate`, `prompt_injection_detected` | ⚠️ Requires Jev/TypeSafe/OpenRouter credential; `_run_all` reports `skipped_no_credentials` when absent |
| **Integration** | `integration_dataset.jsonl` (13 cases, incl. int_013) | `contract_valid`, `no_mismatch` | ✅ Implemented |
| **Multi-turn** | `conversations.jsonl` (13 conversations) | `turn_success_rate`, `conversation_success_rate`, `tool_call_validity`, `context_retention` | ⚠️ Real LLM path (`RealAgentRunner`); skipped gracefully without LLM credentials |
| **Planner backlog** (opt-in) | `planner_dataset_backlog.jsonl` (6 cases) | Same planner metrics; cases document unsupported features (`metadata.backlog`, `metadata.limitation`) | ⏸️ `run_backlog: false` default → `skipped_backlog`; set `true` in `component_benchmarks.yaml` to run |

**Run all**: `PYTHONPATH=. python scripts/evaluation/run_component_benchmarks.py` (or `python -m package.evaluation.component._run_all`)
### 0.4.3. Agent Evaluation (5-Layer Framework + Campaign)

| Layer | Focus | Key Metrics |
|-------|-------|-------------|
| **L1: Outcome** | Recommendation quality | precision@k, recall@k, hit_rate@k, ndcg@k, mrr@k, map@k, seen_item_rate, retrieval funnel |
| **L2: Interaction** | Output quality | task_success (v2, kind-specific), constraint_satisfaction, asked_clarification, exclusion_compliance |
| **L3: Grounding** | Faithfulness | answer_grounded, answer_fallback, retrieval diagnostics |
| **L4: Process** | Planning quality | tool_selection_ok, argument_ok, plan_validity, reflection_triggered, reflection_rescued |
| **L5: Deployment** | Latency/cost | wall_seconds, token usage, provider_error_rate |

**Orchestration**: Campaign runner (`package/evaluation/campaign/campaign_runner.py`) manages parameter grids, comparison pairs, and repetitions across multiple `run_agent_eval.py` experiments.

**Run**: `PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --eval-on validation [--resume] [--domain Video_Games]`

### 0.4.4. Key Directories (configs/path/data_paths.yaml)

| Category | Path (relative to repo root) | Accessor |
|----------|------------------------------|----------|
| Source root | `.` | `get_data_paths().src_root` |
| Config dir | `configs/` | `get_data_paths().config_dir` |
| Pipeline data | `resource/{raw,cleaned,filtered,mapped,splits,item_knn,corpus}/` | `get_data_paths().cleaned_path(domain)`, etc. |
| Logs | `experiments/logs/<tag>/` | `get_data_paths().log_dir` |
| Experiment outputs | `experiments/` subdirs (see `outputs:` section) | `get_data_paths().output_dir("agent_eval")`, etc. |---

## 0.5. Recommendation Foundation (Updated)

### 0.5.1. Embedding — **NOT IMPLEMENTED in runtime**

**Status**: `package/embeddings/__init__.py` exists but is **optional dense retrieval primitives** — not wired into the agent tool chain [[evidence: embeddings/__init__.py lines 1-10]].

- **Runtime has no model dependency**: callers provide an encoder or vectors; offline model pinning and catalog encoding remain in `scripts/evaluation/` [[evidence: embeddings/__init__.py lines 3-4]].
- **Current retrieval**: **SQLite FTS5 + BM25** over `title`, `store`, `main_category`, `categories` (lexical only) — no embedding-based retrieval in the agent tool chain.
- **BPR-MF recommender** uses embeddings internally but is separate from candidate retrieval (evaluation only).
- **Files in `package/embeddings/`** (available but not used by agents):
  - `encoder.py` — `Encoder` class (TextEncoder alias) [[evidence: encoder.py lines 1-12]]
  - `text_encoder.py` — `TextEncoder` contract for encoding sequences [[evidence: text_encoder.py lines 1-31]]
  - `vector_store.py` — `VectorStore` for dense vector index with cosine similarity search [[evidence: vector_store.py lines 1-104]]
  - `__init__.py` — exports `TextEncoder`, `VectorStore` [[evidence: embeddings/__init__.py lines 7-10]]

> **Note**: `package/tools/embeddings/__init__.py` **does NOT exist**. The embeddings module lives at `package/embeddings/`, not under `tools/`.

### 0.5.2. Retrieval

**Implementations** (6 tools distributed across subpackages):

| Tool | File | Input | Output (keys for `$N.path`) | Depends On |
|------|------|-------|------------------------------|------------|
| `SearchTool` | `package/tools/retrieval/search_tool.py` [[evidence: retrieval/search_tool.py]] | `query` (English), `filters`, `limit` | `candidates` (w/ score), `total_matches`, `query_tokens`, `truncated`, `applied_filters` | Corpus (FTS5+BM25) |
| `FilterTool` | `package/tools/sql/filter_tool.py` [[evidence: sql/filter_tool.py]] | `filters`, `order_by`, `limit` | `candidates`, `total_matches`, `truncated`, `applied_filters` | Corpus |
| `SimilarTool` | `package/tools/ranking/similar_tool.py` [[evidence: ranking/similar_tool.py]] | `items` (seed), `top_k`, `domain`, `exclude_input` | `candidates` (item_id, similarity, domain), `unknown_items` | ItemKNN similarity |

**Query preprocessing**: `_tokenize` (lowercase, `\w`-only, ASCII-fold for Unicode). Tokens double-quoted for FTS5 safety.

**Candidate generation**: Tools return `candidates` list with `item_id`, metadata, and `score` (BM25 or similarity). Planner combines via `$N.path` references.

**Top-K**: Configurable per tool, capped at `MAX_CANDIDATES` (default 100). `SEMANTIC_DEFAULT_LIMIT` = 50.

### 0.5.3. Ranking

**Architecture**: `CandidateScorer` protocol → `BaselineScorer` adapter → `RankTool`

| Scorer | Signal | Cold-start handling |
|--------|--------|---------------------|
| **Popularity** | Global item popularity (interaction count) | Works for all users |
| **ItemKNN** | Item-item collaborative filtering (cosine similarity) | Falls back to popularity |
| **BPR-MF** | Bayesian Personalized Ranking (matrix factorization) | Evaluation only (offline) |

**BaselineScorer** combines popularity (tiny weight 1e-6 for tie-breaking) + ItemKNN CF signal. Users with no CF signal get popularity only.

**RankTool output**: `ranked` (rank, item_id, score, domain), `model` name, `cold_start` flag, `excluded_seen`, `unscored_item_ids`, `has_personal_signal`, `note` (explanation if empty).

**Provenance**: `fit_provenance.py`, `file_hash.py`, `mapping_hash.py`, `fit_split_names.py` track artifact reproducibility.---

## 0.6. Agentic Layer (Updated)

### 0.6.1. Tools (6 controlled operations) — with Planner? column

| Tool | Group | File | Input | Output (keys for `$N.path`) | Depends On | **Planner?** |
|------|-------|------|-------|------------------------------|------------|--------------|
| `SearchTool` | Retrieval | `package/tools/retrieval/search_tool.py` | `query` (English), `filters`, `limit` | `candidates` (w/ score), `total_matches`, `query_tokens`, `truncated`, `applied_filters` | Corpus (FTS5+BM25) | **Yes** |
| `FilterTool` | Retrieval | `package/tools/sql/filter_tool.py` | `filters`, `order_by`, `limit` | `candidates`, `total_matches`, `truncated`, `applied_filters` | Corpus | **Yes** |
| `SimilarTool` | Retrieval | `package/tools/ranking/similar_tool.py` | `items` (seed), `top_k`, `domain`, `exclude_input` | `candidates` (item_id, similarity, domain), `unknown_items` | ItemKNN similarity | **Yes** |
| `RankTool` | Ranking | `package/tools/ranking/rank_tool.py` | `user_id`, `candidates`, `top_k`, `exclude_seen` | `ranked`, `model`, `cold_start`, `excluded_seen`, `unscored_item_ids`, `has_personal_signal` | CandidateScorer | **Yes** |
| `LookupTool` | Hydration | `package/tools/sql/lookup_tool.py` | `item_ids` OR `query` (SELECT), `max_rows` | `items`, `missing_item_ids`, `truncated` | Corpus | **Yes** |
| `MemoryTool` | Memory | `package/memory/memory_tool.py` | `user_id`, `top_n_categories` | `user_id`, `known`, `n_interactions`, `top_categories`, `price_range`, `recent_items`, `love/hate_categories`, `loved/hated_items` | Interactions + Corpus | **No** (only `planner_memory`) |

> **Evidence for Planner? column**: `package/agents/toolkit/agent_tools.py` lines 22-26:
> ```python
> def for_planner(self) -> list[Tool]:
>     return [self.item_cf, self.reco, self.query, self.search, self.sql]  # SimilarTool, RankTool, LookupTool, SearchTool, FilterTool
>
> def for_planner_memory(self) -> list[Tool]:
>     return [*self.for_planner(), self.memory]  # + MemoryTool
> ```
> MemoryTool is **only** in `for_planner_memory()`, not in `for_planner()`.

**Retrieval → Ranking → Hydration**: Retrieval finds *which items might be relevant*; Ranking orders *which of these candidates are best*; Hydration fetches metadata for *known IDs*.

### 0.6.2. MemoryTool

**File**: `package/memory/memory_tool.py` [[evidence: memory/memory_tool.py]]

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

### 0.6.3. Inference Layer (`package/inference/`)

| Component | File | Purpose |
|-----------|------|---------|
| **compose_llm** | `package/inference/compose/compose_llm.py` [[evidence: compose/compose_llm.py lines 1-70]] | LLM writes final answer from agent's `recommended` items. Validated by `check_grounding`. Retries up to `llm_retries`. Falls back to template on failure. |
| **compose_template** | `package/inference/compose/compose_template.py` [[evidence: compose/compose_template.py lines 1-42]] | Deterministic template fallback (no LLM call). Formats items with title, price, rating, store. |
| **grounding** | `package/inference/grounding/check_grounding.py` [[evidence: grounding/check_grounding.py lines 1-28]] | Checks: mentioned IDs ⊆ recommended IDs, bare ASINs, price/rating numbers within `price_tolerance`. Returns error string or None. |

**Inference modes** (from `configs/agent/inference.yaml`):
- `mode: llm` — LLM answer with grounding check + retry
- `mode: template` — Deterministic, no LLM

### 0.6.4. Configs: `configs/agent/*.yaml` (11 files)

| File | Purpose |
|------|---------|
| `ablation.yaml` | Ablation experiment settings |
| `agent.yaml` | PlanExecutor limits (max_steps, plan_retries, reflect_rounds, reflect_quality_threshold, max_tokens, temperature) |
| `agent_eval.yaml` | Agent evaluation config (agents list, k, per_segment, n_ambiguous, language, price_slack, etc.) |
| `demo.yaml` | Gradio demo settings |
| `demo_profiles.yaml` | Demo user profiles |
| `inference.yaml` | Inference mode (llm/template), llm_retries, check_numbers, price_tolerance, max_tokens, temperature |
| `llm.yaml` | LLM provider config (base_url, model, api_key, timeout) |
| `memory.yaml` | MemoryTool limits (top_n_categories, top_n_recent, rating thresholds) |
| `reference_plans.yaml` | Reference plans for evaluation |
| `scoring.yaml` | Scorer weights (popularity_weight, itemcf_weight, hybrid_weight) |
| `tools.yaml` | Tool limits (max_candidates, semantic_default_limit, filter limits, etc.) |

> **Evidence**: Directory listing of `configs/agent/` shows exactly 11 `.yaml` files [[evidence: Get-ChildItem output]].

### 0.6.5. Multi-turn

**Status**: `package/evaluation/multi_turn/_run.py` exists with 11 conversations, but `mock: true` — **not real-LLM evaluation**. Framework exists but real provider verification pending. MockAgentRunner still exists (Phase E skipped).---

## 0.7. End-to-End Data Flow (Example: Planner Agent)

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

## 0.8. Evaluation Framework (Updated)

### 0.8.1. Five-Layer Architecture (package/evaluation/)

| Layer | Module | Focus | Key Metrics |
|-------|--------|-------|-------------|
| **L1: Outcome** | `layer1_outcome/score_layer1_outcome.py` | Recommendation quality | precision@k, recall@k, hit_rate@k, ndcg@k, mrr@k, map@k, seen_item_rate, retrieval funnel |
| **L2: Interaction** | `layer2_interaction/score_layer2_interaction.py` | Output quality | task_success (v2, kind-specific), constraint_satisfaction, asked_clarification, exclusion_compliance |
| **L3: Grounding** | `layer3_grounding/score_layer3_grounding.py` | Faithfulness | answer_grounded, answer_fallback, retrieval diagnostics (target_in_pool, retrieved_by_*, stage_lost) |
| **L4: Process** | `layer4_process/score_layer4_process.py` | Planning quality | tool_selection_ok, argument_ok, plan_validity, reflection_triggered, reflection_rescued |
| **L5: Deployment** | `layer5_deployment/score_layer5_deployment.py` | Latency/cost | wall_seconds, token usage, provider_error_rate |

**Entry point**: `package/evaluation/trajectory/score_trajectory.py` orchestrates all 5 layers per trajectory, then merges retrieval-funnel and stage-loss diagnostics. `summarize.py` aggregates scored rows into `agent → kind → segment → mean` (with `_NON_NUMERIC_KEYS` exclusions and `_PERCENTILE_COLUMNS` p50/p95).

> **Complete per-module/per-def reference: see §0.17 (Evaluation System — Complete Reference), including the full scored-column catalog, every diagnostics/reporting/judge/ablation/campaign module, all eval scripts, the test-coverage map, and the known-issues register (§0.17.20).**

### 0.8.2. Component Benchmarks (package/evaluation/component/) — 6 Components

**5 isolated component evaluators** with JSONL datasets + **multi-turn conversation evaluation**:

| Component | Dataset | Key Metrics | Status |
|-----------|---------|-------------|--------|
| **Memory** | `memory_correctness_dataset.jsonl` (29 cases) | known_correct, n_interactions_correct, top_categories_exact, loved_items_exact (0.5), all_fields_match (0.933), future_leakage (0) | ✅ Works (mock tools) |
| **Planner** | `planner_dataset.jsonl` (29 cases) | tool_selection_accuracy, argument_correctness, plan_validity, constraint_handling, clarification_precision, refusal_to_guess | ✅ Implemented (requires LLM) |
| **Executor** | `executor_dataset.jsonl` (22 cases) | all_steps_ok, reflection_rescued, reflection_triggered | ✅ Implemented (mock LLM + controlled tools) |
| **Grounding** | `grounding_dataset.jsonl` (35 cases) | claims_supported, grounding_rate, hallucination_rate, prompt_injection_detected | ✅ Implemented (ScriptedJudge); skipped w/o Jev credential |
| **Integration** | `integration_dataset.jsonl` (13 cases) | contract_valid, no_mismatch | ✅ Implemented |
| **Multi-turn** | `conversations.jsonl` (13 conversations) | turn_success_rate, conversation_success_rate, tool_call_validity, context_retention | ⚠️ Real LLM (`RealAgentRunner`); `skipped_no_credentials` without LLM |
| **Planner backlog** | `planner_dataset_backlog.jsonl` (6 cases, opt-in) | planner metrics; `metadata.backlog`/`limitation` mark unsupported features | ⏸️ `run_backlog: false` → `skipped_backlog` |

**Unified runner**: `package/evaluation/component/_run_all.py` → subprocesses each component CLI (`package/evaluation/component/run_benchmark_cli.py`) → aggregates into `unified_report_*.json/.md` in `experiments/agent_eval/component_benchmarks/`.

**Config**: `configs/eval/component_benchmarks.yaml` defines `datasets` map (component → dataset path), `runs` (iterations per case), and per-component `configs` (thresholds, use_jev, etc.).
### 0.8.3. Test Doubles (tests/agents/fakes/)

> **Note**: The `package/evaluation/doubles/` directory referenced in earlier docs **does not exist** in the current structure. Test doubles live in `tests/agents/fakes/`:

| Double | File | Purpose |
|--------|------|---------|
| **ScriptedLLM** | `tests/agents/fakes/scripted_llm.py` | Returns pre-scripted LLM responses for testing |
| **FakeSimilarTool** | `tests/agents/fakes/fake_tools.py` | Deterministic SimilarTool for benchmarks |
| **FakeRankTool** | `tests/agents/fakes/fake_tools.py` | Deterministic RankTool for benchmarks |
| **FakeLookupTool** | `tests/agents/fakes/fake_tools.py` | Deterministic LookupTool for benchmarks |
| **FakeSearchTool** | `tests/agents/fakes/fake_tools.py` | Deterministic SearchTool for benchmarks |
| **FakeFilterTool** | `tests/agents/fakes/fake_tools.py` | Deterministic FilterTool for benchmarks |
| **FakeMemoryTool** | `tests/agents/fakes/fake_tools.py` | Deterministic MemoryTool for benchmarks |

**ScriptedJudge** is implemented inline in `package/evaluation/component/benchmarks/grounding_benchmark.py` as a test double for Jev.

### 0.8.4. Trajectory Scoring (package/evaluation/trajectory/)

| File | Purpose |
|------|---------|
| `score_trajectory.py` | Orchestrates all 5 layers per trajectory; returns `TrajectoryScores` |
| `summarize.py` | Aggregates per-trajectory scores into experiment-level summaries |

### 0.8.5. Product Reply Evaluation (package/evaluation/product_reply/)

| File | Purpose |
|------|---------|
| `evaluate_product_reply.py` | Deterministic heuristic evaluator: claim extraction + per-claim support check vs item fields + 4-axis communication scoring (relevance/clarity/language/honesty, 1–5). Standalone CLI — NOT wired into agent_eval. `_score_language` is an ASCII-script heuristic, explicitly not language detection. |
| `evaluate_product_reply_with_jev.py` | LLM-as-judge (Jev/TypeSafe AI): faithfulness (claim extraction + Noul support questions) + communication quality (Score questions). Used by (a) component `grounding` benchmark on synthetic cases, and (b) `package/evaluation/judge/evaluate_trajectories_with_jev.py` — the post-hoc Jev pass wired into `run_agent_eval`/`campaign` (`agent_eval.jev`, opt-in, credential-gated). |

### 0.8.6. Campaign Runner (package/evaluation/campaign/)

| File | Purpose |
|------|---------|
| `campaign_runner.py` | Orchestrates multiple `run_agent_eval.py` experiments via subprocess; parameter grid expansion, comparison pairs, repetition |
| `checkpoint_manager.py` | Resume/crash recovery for long-running campaigns |
| `_schema.py` | Pydantic schemas for campaign config, experiment config, comparison pairs |

**Config**: `configs/eval/campaign.yaml` (parameter_grid, comparison_pairs, repetition_count, output_dir, per-experiment timeout — now 7200s, `multi_turn` policy never/once/all, `ablation.contrasts`)

**Post-run wiring (added 2026-11-16)**: after comparisons, configured `ablation.contrasts` run automatically via `run_ablation_contrasts` → `<campaign_dir>/ablation/<contrast>/` artifacts + `campaign_result.json["ablation"]` statuses (subset runs skip + preserve). Per-experiment opt-ins: `agent_config.multi_turn`, `agent_config.jev` (both normalized into the config overlay; explicit `enabled:false` prevents base-yaml leakage into grid runs). `evaluation_config` accepts `per_segment` + `request_scope` (mapped into the agent_eval overlay — campaign.yaml sets `request_scope: "all"` for oracle coverage).

**CLI**: `PYTHONPATH=. python scripts/evaluation/run_campaign.py [--campaign-config PATH] [--only 7,8,11,12] [--dry-run] [--git-sha SHA]` — `--only` runs a subset of grid experiments while preserving completed ones (merge, not overwrite). Campaign overlays may set `agent_eval.exclude_tools` for tool-subset ablations.

**Status**: `campaign_001` (grid `campaign_001_parameter_grid`, 12 experiments) completed 12/12 successful; experiments 7/8/11/12 (planner/planner_memory with reflect + multi_turn) were resumed via `--only` after timeout, yielding 132 trajectory records each.

### 0.8.7. Multi-turn Evaluation (package/evaluation/multi_turn/)

| File | Purpose |
|------|---------|
| `_run.py` | CLI entrypoint (`run_multi_turn_cli`) — requires real LLM (RealAgentRunner); fails loudly if no provider |
| `multi_turn_evaluator.py` | Core evaluation logic over conversations |
| `_agent_runner.py` | `RealAgentRunner` (PlanExecutor + Session), `MockAgentRunner` (Phase E skipped) |
| `_eval_step.py` | Per-turn evaluation metrics |
| `_reporting.py` | Report generation |
| `_schema.py` | Conversation, Turn, EvaluationSummary schemas |
| `conversations.jsonl` | 13 conversation fixtures (incl. 2 negative cases) |

**Status**: Per-turn metrics repaired (expect_* handling, resolved_config propagation); `RealAgentRunner` is the production path and requires `LLM_BASE_URL` + `LLM_API_KEY` — reports `skipped_no_credentials` when absent. `MockAgentRunner` retained for tests.---

## 0.9. Configuration Architecture

### 0.9.1. Centralized Path Management (configs/path/data_paths.yaml)

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
  example_report: "agent_eval/example_report"
  test_logs: "test_logs"
```

**Access in code**: `get_data_paths().corpus_path`, `get_data_paths().output_dir("agent_eval")`, etc.

### 0.9.2. Configuration Loading (package/config/load_config.py)

- `load_config("agent/llm")` → loads `configs/agent/llm.yaml` with Pydantic validation
- **Overlay support**: `CONFIG_OVERLAY_PATH` env var points to YAML that overrides base config (used by campaign runner)
- **Env var expansion**: `${VAR:-default}` syntax in YAML (e.g., `${LLM_BASE_URL:-}`)
- **Strict schemas**: `extra="forbid"` — unknown keys raise error
- **All scripts use `load_config`** — no direct `yaml.safe_load` (enforced by Jev reliability fix)

### 0.9.3. Key Config Files (Verified Inventory)

| Directory | Files | Purpose |
|-----------|-------|---------|
| `configs/agent/` | `agent.yaml`, `llm.yaml`, `agent_eval.yaml`, `inference.yaml`, `demo.yaml`, `demo_profiles.yaml`, `memory.yaml`, `tools.yaml`, `scoring.yaml`, `ablation.yaml`, `reference_plans.yaml` | Agent limits, LLM provider, eval agents, inference mode, demo settings, memory config, tool runtime limits, scorer mode, ablation agents, planner reference plans |
| `configs/data/` | `cleaning.yaml`, `filtering.yaml`, `split.yaml` | Pipeline stages 1–4 |
| `configs/eval/` | `component_benchmarks.yaml`, `judge.yaml`, `baselines.yaml`, `candidate_recall.yaml`, `memory_utility.yaml`, `ranking_eval.yaml`, `ranking_diagnostics.yaml`, `tool_validation.yaml`, `tuning.yaml`, `recommendation_metrics.yaml`, `segment_thresholds.yaml`, `semantic_candidate_pilot.yaml`, `sparse_content_eval.yaml`, `sparse_seed_eval.yaml`, `policy_acceptance.yaml` | Component benchmarks, Jev judge, baseline models, recall budgets, ranking eval, diagnostics, tool validation, hyperparameter tuning, metrics K-values, segment thresholds, semantic/sparse pilots |
| `configs/eval/` | `campaign.yaml` | Campaign orchestration (parameter grid, comparison pairs, repetition) |
| `configs/path/` | `data_paths.yaml`, `domains.yaml`, `run_tag.yaml` | All filesystem paths, domain list, run tag for artifact directories |---

## 0.10. Scripts and Execution Workflows

### 0.10.1. Primary Entry Points

| Script | Purpose | Key Configs | Key CLI Flags |
|--------|---------|-------------|---------------|
| `scripts/evaluation/run_agent_eval.py` | Full agent evaluation (ranking + agent metrics) | `agent_eval.yaml`, `agent.yaml`, `inference.yaml`, `eval/baselines.yaml` | `--domain`, `--eval-on`, `--resume` |
| `scripts/evaluation/run_component_benchmarks.py` | All 6 component benchmarks + unified report | `eval/component_benchmarks.yaml` | (none — thin wrapper over `_run_all.py`) |
| `package/evaluation/component/run_benchmark_cli.py` | Single component benchmark | `eval/component_benchmarks.yaml` (per-component) | `--component`, `--dataset`, `--tags`, `--metadata`, `--git-sha` |
| `scripts/evaluation/run_campaign.py` | Campaign orchestration | `evaluation/campaign.yaml` | `--campaign-config`, `--dry-run`, `--git-sha` |
| `scripts/data_pipeline/run_pipeline.py` | Data pipeline (stages 1–4) | `data/cleaning.yaml`, `data/filtering.yaml`, `data/split.yaml`, `path/data_paths.yaml` | `--stages`, `--domain`, `--force`, `--cold-start-report`, `--skip-corpus`, `--skip-item-knn`, `--review-path`, `--allow-manifest-mismatch`, `--scratch-dir` |
| `scripts/evaluation/ranking_eval.py` | Ranking evaluation (Popularity, ItemKNN, BPR-MF) | `eval/ranking_eval.yaml`, `eval/baselines.yaml` | `--eval-on`, `--domain`, `--model`, `--force` |
| `scripts/evaluation/candidate_recall.py` | Candidate recall experiments | `eval/candidate_recall.yaml` | `--eval-on`, `--domain`, `--force` |
| `scripts/demo/run_demo.py` | Gradio demo (mock/live) | `agent/demo.yaml`, `agent/inference.yaml` | `--domain`, `--host`, `--port` |
| `scripts/tools/run_tools.py` | Direct tool validation (no LLM, no agent) | `eval/tool_validation.yaml`, `eval/baselines.yaml` | `--domain`, `--tool`, `--args`, `--chain`, `--init-args`, `--interactions`, `--list` |
| `scripts/tools/check_llm_provider.py` | LLM provider connectivity test | `agent/llm.yaml` | (none) |
| `scripts/experiments/compare_experiments.py` | Compare experiment pairs (ablation) | — | `--contrast` |
| `scripts/evaluation/jev_smoke_test.py` | Real Jev provider smoke test | `eval/judge.yaml` | (requires `TYPESAFE_API_KEY`) |
| `scripts/llm_agent/smoke_real_llm.py` | Real LLM agent smoke test | `agent/llm.yaml`, `agent/agent.yaml` | `--domain`, `--text` |
| `scripts/eda_diagnostic/run_eda.py` | EDA on raw data | — | `--domain`, `--sample` |
| `scripts/eda_diagnostic/diagnose_splits.py` | Split diagnostics | — | `--domain`, `--tag` |

### 0.10.2. Execution Conventions

- **All scripts require `PYTHONPATH=.`** (pytest sets via `pyproject.toml`; direct runs need explicit)
- **No CLI override flags** — all tunables in YAML (enforced by refactor)
- **Tag-based runs**: `run_tag.yaml` controls `filtered_dir`, `mapped_dir`, `splits_dir`, `corpus_dir`, `item_knn_dir`
- **Resume support**: `run_agent_eval.py --resume` continues from existing trajectory file
- **Mock mode**: `--mock` flag on `run_demo.py`; component benchmarks use ScriptedLLM/Fake*Tool internally (no flag); campaign runner supports `--mock` for testing without real data/LLM---

## 0.11. Script Reference Details

### 0.11.1. Data Pipeline (Phase 3)

**`scripts/data_pipeline/run_pipeline.py`** — Run the full data pipeline or selected stages.

```bash
# Run all stages (1→2→3→4)
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py

# Run specific stages
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages 1
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages 1,2
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages 2,3,4

# Run for specific domains (default: all domains in domains.yaml)
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --domain Video_Games
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --domain Video_Games --domain Toys_and_Games

# Override run tag (default: tag from configs/path/run_tag.yaml)
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --tag my_run_v1

# Force overwrite existing outputs
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --force

# Stage 1 options
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages 1 --domain Video_Games --review-path /path/to/review_Video_Games.jsonl.gz

# Stage 2 options
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages 2 --cold-start-report

# Stage 4 options
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages 4 --skip-corpus
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages 4 --skip-item-knn
```

**Arguments**:

| Arg | Default | Description |
|-----|---------|-------------|
| `--stages` | `all` | Stages to run: `all`, `1`, `2`, `3`, `4`, or comma-separated (e.g., `1,2`, `2,3`). Always run in order 1→2→3→4. |
| `--domain` | all from `domains.yaml` | Domain name(s) (repeat for multiple). Single domain → bundle named after it; subsets rejected. |
| `--tag` | from `run_tag.yaml` | Run tag for data bundle. |
| `--force` | false | Overwrite existing outputs. |
| `--cold-start-report` | false | Print cold-start statistics for stage 2 (expensive). |
| `--skip-corpus` | false | Skip corpus building in stage 4. |
| `--skip-item-knn` | false | Skip ItemKNN building in stage 4. |
| `--review-path` | auto | Override review path for stage 1 (only with `--domain` single and `--stages 1`). |
| `--allow-manifest-mismatch` | false | Continue after upstream manifest mismatch/missing manifest. |
| `--scratch-dir` | auto | Scratch directory for disk-backed Stage 3 (temporal_train_core). |
### 0.11.2. Agent Evaluation

**`scripts/evaluation/run_agent_eval.py`** — Full agent evaluation (ranking + agent metrics).

```bash
# Run on validation split
PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --eval-on validation

# Resume interrupted run
PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --resume

# Run on test split (use sparingly)
PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --eval-on test

# Single domain
PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --domain Video_Games --eval-on validation
```

**Arguments**:

| Arg | Default | Description |
|-----|---------|-------------|
| `--domain` | all from `domains.yaml` | Domain bundle (repeat for multiple). Single domain → bundle named after it. |
| `--eval-on` | `validation` | Split to evaluate on: `validation` or `test`. |
| `--resume` | false | Reuse existing trajectory file (same request text, agent, reflect_rounds, inference_mode). |

### 0.11.3. Component Benchmarks

**`scripts/evaluation/run_component_benchmarks.py`** — Run all 6 component benchmarks + unified report.

```bash
PYTHONPATH=. python scripts/evaluation/run_component_benchmarks.py
```

**`package/evaluation/component/run_benchmark_cli.py`** — Single component benchmark.

```bash
# Run memory benchmark
PYTHONPATH=. python -m package.evaluation.component.run --component memory --dataset package/evaluation/component/benchmarks/memory_correctness_dataset.jsonl

# Run planner benchmark (requires LLM)
PYTHONPATH=. python -m package.evaluation.component.run --component planner --dataset package/evaluation/component/benchmarks/planner_dataset.jsonl

# Run with tags filter
PYTHONPATH=. python -m package.evaluation.component.run --component executor --dataset package/evaluation/component/benchmarks/executor_dataset.jsonl --tags warm cold
```

**Arguments**:

| Arg | Required | Description |
|-----|----------|-------------|
| `--component` | Yes | Component name: `memory`, `planner`, `executor`, `grounding`, `integration` |
| `--dataset` | Yes | Path to benchmark dataset (JSON/JSONL) |
| `--tags` | No | Filter cases by tags (OR logic) |
| `--metadata` | No | Filter cases by metadata (key=value, AND logic) |
| `--git-sha` | No | Git commit SHA (auto-detected) |
### 0.11.4. Campaign Runner

**`scripts/evaluation/run_campaign.py`** — Campaign orchestration.

```bash
# Run with default campaign config
PYTHONPATH=. python scripts/evaluation/run_campaign.py

# Dry run (print what would execute)
PYTHONPATH=. python scripts/evaluation/run_campaign.py --dry-run

# Custom campaign config
PYTHONPATH=. python scripts/evaluation/run_campaign.py --campaign-config /path/to/campaign.yaml
```

**Arguments**:

| Arg | Default | Description |
|-----|---------|-------------|
| `--campaign-config` | `configs/eval/campaign.yaml` | Path to campaign YAML |
| `--dry-run` | false | Print experiments without executing |
| `--git-sha` | auto-detected | Git commit SHA for reproducibility |

### 0.11.5. Demo

**`scripts/demo/run_demo.py`** — Gradio UI demo.

```bash
# Mock mode (no data/LLM needed) — requires --mock flag
PYTHONPATH=. python scripts/demo/run_demo.py --mock

# Live mode with real data
PYTHONPATH=. python scripts/demo/run_demo.py --domain Video_Games

# Live mode options
PYTHONPATH=. python scripts/demo/run_demo.py --domain Video_Games --host 0.0.0.0 --port 7860
```

**Arguments**:

| Arg | Default | Description |
|-----|---------|-------------|
| `--mock` | false | Mock mode (no data/LLM needed) |
| `--domain` | required in live | Domain name (repeat for multiple) |
| `--host` | `127.0.0.1` | Gradio host |
| `--port` | `7860` | Gradio port |

> **Note**: `eval_on`, `use_prebuilt_corpus`, `allow_missing_corpus_sources`, `inference_mode` are read from `configs/agent/demo.yaml` and `configs/agent/inference.yaml` — not CLI flags.

### 0.11.6. Tool Validation & Runner

**`scripts/tools/run_tools.py`** — Direct tool validation (no LLM, no agent).

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

**Arguments**:

| Arg | Default | Description |
|-----|---------|-------------|
| `--domain` | all from `domains.yaml` | Domain bundle |
| `--tool` | (required if not `--list`/`--chain`) | Tool name: `SearchTool`, `FilterTool`, `SimilarTool`, `RankTool`, `LookupTool`, `MemoryTool` |
| `--args` | `{}` | JSON args for the tool |
| `--chain` | — | Chain multiple tools (space-separated) |
| `--init-args` | `{}` | JSON init args for chained tools |
| `--interactions` | from splits | Override interactions parquet for MemoryTool |
| `--list` | false | List available tools and exit |

**`scripts/tools/check_llm_provider.py`** — Quick LLM provider connectivity test.

```bash
PYTHONPATH=. python scripts/tools/check_llm_provider.py
```
### 0.11.7. Config Reference (Fixed Table)

All tunable parameters live in YAML. CLI flags are only operational selectors (`--tag`, `--domain`, `--eval-on`, `--resume`, `--work-dir`, `--candidates-from`, `--stages`, `--force`, `--mock`, `--host`, `--port`, `--campaign-config`, `--dry-run`, `--git-sha`, `--tool`, `--args`, `--chain`, `--init-args`, `--interactions`, `--list`, `--contrast`, `--component`, `--dataset`, `--tags`, `--metadata`, `--review-path`, `--cold-start-report`, `--skip-corpus`, `--skip-item-knn`, `--allow-manifest-mismatch`, `--scratch-dir`).

| Config Key (load_config arg) | File Path | Purpose |
|------------------------------|-----------|---------|
| `agent/agent` | `configs/agent/agent.yaml` | PlanExecutor limits (max_steps, reflect_rounds, tokens, temperature) |
| `agent/llm` | `configs/agent/llm.yaml` | Provider, model, base_url, api_key, timeout |
| `agent/agent_eval` | `configs/agent/agent_eval.yaml` | Agents list, request_scope, per_segment, trajectory_file, multi_turn.enabled |
| `agent/inference` | `configs/agent/inference.yaml` | Inference mode (llm/template), llm_retries, price_tolerance |
| `agent/demo` | `configs/agent/demo.yaml` | Demo eval_on, use_prebuilt_corpus, allow_missing_corpus_sources |
| `agent/memory` | `configs/agent/memory.yaml` | MemoryTool thresholds (love/hate rating), top_n_categories |
| `agent/tools` | `configs/agent/tools.yaml` | Tool runtime limits (max_steps, etc.) |
| `agent/scoring` | `configs/agent/scoring.yaml` | Scorer mode (baseline/hybrid), hybrid_popularity_weight |
| `agent/ablation` | `configs/agent/ablation.yaml` | Ablation agent variants |
| `agent/reference_plans` | `configs/agent/reference_plans.yaml` | Planner reference plans for constrained kinds |
| `data/cleaning` | `configs/data/cleaning.yaml` | Stage 1: cleaning parameters |
| `data/filtering` | `configs/data/filtering.yaml` | Stage 2: filtering parameters |
| `data/split` | `configs/data/split.yaml` | Stage 3: split protocol, item_knn_splits, data_protocol |
| `eval/component_benchmarks` | `configs/eval/component_benchmarks.yaml` | Component benchmark runs, datasets map, per-component configs |
| `eval/judge` | `configs/eval/judge.yaml` | Jev provider config (api_key, model, timeout, criteria) |
| `eval/baselines` | `configs/eval/baselines.yaml` | Baseline model configs (popularity, item_knn, bpr_mf) |
| `eval/candidate_recall` | `configs/eval/candidate_recall.yaml` | Recall budgets, candidate sources |
| `eval/ranking_eval` | `configs/eval/ranking_eval.yaml` | Ranking eval settings |
| `eval/ranking_diagnostics` | `configs/eval/ranking_diagnostics.yaml` | Bottleneck analysis settings |
| `eval/tool_validation` | `configs/eval/tool_validation.yaml` | run_tools.py settings (model, eval_users, negatives, seed) |
| `eval/memory_utility` | `configs/eval/memory_utility.yaml` | Memory utility analysis settings |
| `eval/recommendation_metrics` | `configs/eval/recommendation_metrics.yaml` | K values, metrics list |
| `eval/segment_thresholds` | `configs/eval/segment_thresholds.yaml` | Segment thresholds (warm/cold/sparse) |
| `eval/tuning` | `configs/eval/tuning.yaml` | Hyperparameter grids |
| `eval/semantic_candidate_pilot` | `configs/eval/semantic_candidate_pilot.yaml` | Semantic candidate pilot settings |
| `eval/sparse_content_eval` | `configs/eval/sparse_content_eval.yaml` | Sparse content eval settings |
| `eval/sparse_seed_eval` | `configs/eval/sparse_seed_eval.yaml` | Sparse seed eval settings |
| `eval/policy_acceptance` | `configs/eval/policy_acceptance.yaml` | Policy acceptance thresholds |
| `eval/campaign` | `configs/eval/campaign.yaml` | Campaign orchestration (parameter_grid, comparison_pairs, repetition) |
| `path/data_paths` | `configs/path/data_paths.yaml` | All filesystem paths (src_root, config_dir, resource/*, experiments/*) |
| `path/run_tag` | `configs/path/run_tag.yaml` | Current run tag (default: `multi_domain`) |
| `path/domains` | `configs/path/domains.yaml` | Domain list (Video_Games, Toys_and_Games, Electronics) |

### 0.11.8. Output Locations

| Output | Location (relative to `experiments/`) |
|--------|----------------------------------------|
| Pipeline logs | `logs/<tag>/run_pipeline.log` |
| Tool validation log | `logs/<tag>/run_tools.log` |
| Baseline experiments | `baselines/exp_NNN/` |
| Agent eval experiments | `agent_eval/exp_NNN/` |
| Candidate recall experiments | `candidate_recall/exp_NNN/` |
| Ranking eval experiments | `ranking_eval/exp_NNN/` |
| Ranking diagnostics | `ranking_diagnostics/exp_NNN/` |
| Ablation comparisons | `agent_eval/ablation/` |
| Component benchmarks | `agent_eval/component_benchmarks/` (unified_report_*.json/.md) |
| Memory utility analysis | `agent_eval/memory_utility_analysis/` |
| Multi-turn evaluation | `agent_eval/multi_turn/` |
| Test logs / results | `test_logs/` |
| Example reports | `agent_eval/example_report/` |

All of the above are configured in `outputs:` in `configs/path/data_paths.yaml` (relative to `experiments_dir`).

### 0.11.9. Common Patterns

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

### 0.11.10. Config Overlay (per-experiment overrides)

All tunables live in YAML; CLI flags are only operational selectors.

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
CONFIG_OVERLAY_PATH=/path/to/overlay.yaml PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --eval-on validation
```

The campaign runner (`package/evaluation/campaign/`) writes one overlay per experiment automatically. Overlay fragments are deep-merged over the base configs before Pydantic validation, and changing the overlay invalidates cached limits.---

## 0.12. Testing Strategy and Coverage

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
| **Full suite** | `pytest tests/ -q` | **1696 tests collected** (evidence: `python -m pytest --collect-only -q` → `1696 tests collected in 3.07s`) |

**Mock vs. Real Provider**:
- Component benchmarks: **all mocked** (ScriptedLLM, ScriptedJudge, controlled tools)
- Agent evaluation: Can run with real LLM (requires `LLM_BASE_URL`, `LLM_API_KEY`)
- Jev smoke test: `scripts/evaluation/jev_smoke_test.py` for manual real-provider testing---

## 0.13. Known Issues and Bottlenecks

### 0.13.1. Upstream Bottlenecks (Embedding → Retrieval → Ranking)

| Bottleneck | Evidence | Downstream Impact |
|------------|----------|-------------------|
| **No embedding retrieval** | `package/tools/embeddings/__init__.py`: "NOT IMPLEMENTED" | Cold users (72% single-interaction) rely on BM25 over English catalog; Vietnamese semantic gap |
| **BM25 recall unverified** | `candidate_recall` experiments exist but `resource/` data missing | If relevant items not retrieved, ranking cannot promote them |
| **ItemKNN similarity matrix** | Precomputed offline; cold items outside matrix → `unscored_item_ids` | Ranking falls back to popularity for unknown items |
| **Planner tool selection poor** | `tool_selection_accuracy: 0.4904` in component benchmark (unified_report_20261110_210732.md:66) | Wrong tools → wrong candidates → poor ranking input |
| **Executor reflection ineffective** | `reflection_rescued` NOT measured in executor benchmark — benchmark only tests `_execute` (no plan/reflection); see `executor_benchmark.py:8-11` | Failed plans not corrected; quality threshold reflection untested |
| **Grounding rate low** | `grounding_rate: 0.6714` in component benchmark (unified_report_20261110_210732.md:120); `hallucination_rate: 0.3286` | Dummy answer limitation; real answer generation untested |

**Dependency chain verified**: Embedding (absent) → Retrieval (BM25/FTS5) → Ranking (CandidateScorer) → Agent Tools → Agent Response → Grounding. Weak upstream quality propagates downstream.
### 0.13.2. Agentic Layer Issues

| Issue | Evidence | Status |
|-------|----------|--------|
| **Planner LLM produces invalid tool calls** | `tool_selection_accuracy: 0.4904`, `argument_correctness: 0.3842` in component benchmark (unified_report_20261110_210732.md:66-67) | Requires better prompt / few-shot / model |
| **Reflection doesn't rescue failures** | `reflection_rescued` NOT measured in executor benchmark — benchmark scope is `_execute` only (no plan/reflection); reflection tested in unit tests `test_executor_error_taxonomy.py` (ScriptedLLM + fault injection) | Quality threshold reflection (configurable) untested in component benchmark |
| **Grounding rate low** | `grounding_rate: 0.6714`, `hallucination_rate: 0.3286`, `claims_supported: 0.9429` in component benchmark (unified_report_20261110_210732.md:116-121) | ScriptedJudge only; real LLM Jev evaluation requires `TYPESAFE_API_KEY` |
| **Integration latency anomaly** | Mean latency 0.0007s in component benchmark (unified_report_20261110_210732.md:136) — contract-only measurement | Likely contract-only measurement; end-to-end execution time not captured |
| **Multi-turn not real-LLM evaluated** | Multi-turn benchmark ran on **synthetic fixture corpus** (unified_report_20261110_210732.md:152: "measured on the synthetic fixture corpus, not real catalog data"); uses MockAgentRunner | Framework exists, real-LLM evaluation requires `LLM_BASE_URL` + `resource/` data |

### 0.13.3. Evaluation Framework Gaps

| Gap | Evidence | Impact |
|-----|----------|--------|
| **No real-provider agent evaluation** | All component benchmarks mocked (ScriptedLLM, ScriptedJudge, Fake*Tools); planner benchmark requires real LLM but `LLM_BASE_URL` not set | Quality metrics from mocks ≠ real behavior |
| **Campaign runner verified with artifacts** | Campaign `campaign_001` completed 8/12 runs successfully; artifacts in `src/experiments/agent_eval/campaigns/campaign_001/` (campaign_001_summary.md) | Comparative experiments runnable; 4 LLM runs timed out but trajectories saved for resume |
| **Retrieval recall unmeasured** | Environmental blocker: `resource/` data exists at `src/resource/` but BM25 recall experiments not run | Cannot quantify upstream bottleneck |
| **Opik integration PoC only** | No live server, no span instrumentation | Tracing/observability not operational |
| **Provenance incomplete** | `git_sha` empty in unified report (unified_report_20261110_210732.md:50,77,100,124,145,190) | Cannot link results to exact code version |

### 0.13.4. Environmental Blockers

1. **`resource/` data exists at `src/resource/`** — Raw Amazon Reviews 2023 files, cleaned/filtered/mapped/splits, corpus, ItemKNN artifacts all present (verified via directory listing). Required for: agent evaluation, campaign runner, retrieval recall, baseline ranking. Path resolution uses `src_root: "."` in `data_paths.yaml` pointing to `src/`.
2. **`LLM_BASE_URL` / `LLM_API_KEY` not set** — Required for planner benchmark and real agent evaluation.
3. **`TYPESAFE_API_KEY` not set** — Required for real Jev evaluation (grounding benchmark uses ScriptedJudge in CI).---

## 0.14. Limitations and Unverified Areas

| Area | Status | Evidence |
|------|--------|----------|
| **Embedding-based retrieval** | Not implemented | Explicit in code (`package/tools/embeddings/__init__.py`) |
| **Real LLM agent evaluation** | Not verified | Requires `LLM_BASE_URL` + `resource/` data; component benchmarks all mocked |
| **Real Jev grounding evaluation** | Not verified | Requires `TYPESAFE_API_KEY`; grounding benchmark uses ScriptedJudge |
| **Campaign orchestration** | Code verified, artifacts exist | Campaign `campaign_001` ran 8/12 experiments successfully; `src/experiments/agent_eval/campaigns/campaign_001/` contains trajectories, scored.jsonl, summaries |
| **Retrieval recall (BM25 vs. embedding)** | Not measured | Environmental blocker: experiments exist but not executed |
| **Vietnamese/English retrieval gap** | Not measured | Environmental blocker: no recall measurement on real catalog |
| **Multi-turn real-LLM behavior** | Mock only (synthetic fixture corpus) | Framework exists; unified_report_20261110_210732.md:152 confirms synthetic corpus; MockAgentRunner still in place |
| **BPR-MF online serving** | Evaluation only | `package/recommenders/evaluation/bpr_mf_recommender.py` |
| **End-to-end latency profiling** | Anomalous integration latency | Component benchmark shows 0.0007s mean (contract-only measurement) |
| **Provenance (git_sha, config hash)** | Partially implemented | `build_run_provenance.py` exists; `git_sha` empty in unified report |---

## 0.15. Development Workflow

### 0.15.1. Running Tests

```bash
# Full suite
PYTHONPATH=. pytest tests/ -q

# Specific suites
PYTHONPATH=. pytest tests/config/ -v        # 50+ passed (overlay, path resolution, schema validation)
PYTHONPATH=. pytest tests/corpus/ -v        # ItemCorpus build/load/save, FTS5
PYTHONPATH=. pytest tests/data/ -v          # Pipeline stages, leakage checks, mapping
PYTHONPATH=. pytest tests/agents/ -v        # PlanExecutor, Type1Agent, tools, session
PYTHONPATH=. pytest tests/recommenders/ -v  # Popularity, ItemKNN, BPR-MF
PYTHONPATH=. pytest tests/scoring/ -v       # BaselineScorer, CandidateScorer protocol
PYTHONPATH=. pytest tests/tools/ -v         # All 6 tools, corpus, recommenders, scoring
PYTHONPATH=. pytest tests/evaluation/ -v    # Component benchmarks, trajectory scoring, campaign

# With coverage
PYTHONPATH=. pytest tests/ --cov=package --cov-report=term-missing
```

### 0.15.2. Verified CLI Commands

| Command | Verified | Notes |
|---------|----------|-------|
| `PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages 1,2 --domain Video_Games --force` | ✅ | Stages 1→2→3→4; `--cold-start-report`, `--skip-corpus`, `--skip-item-knn`, `--review-path`, `--allow-manifest-mismatch`, `--scratch-dir` |
| `PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --eval-on validation --resume --domain Video_Games` | ✅ | `--resume` reuses trajectories with same request text, agent, reflect_rounds, inference_mode |
| `PYTHONPATH=. python scripts/evaluation/run_component_benchmarks.py` | ✅ | Thin wrapper; runs all 6 components + multi-turn; writes unified_report |
| `PYTHONPATH=. python -m package.evaluation.component.run --component memory --dataset package/evaluation/component/benchmarks/memory_correctness_dataset.jsonl` | ✅ | `--tags`, `--metadata`, `--git-sha` |
| `PYTHONPATH=. python scripts/evaluation/run_campaign.py --dry-run --campaign-config configs/eval/campaign.yaml` | ✅ | `--git-sha` auto-detected |
| `PYTHONPATH=. python scripts/demo/run_demo.py --mock` | ✅ | `--domain`, `--host`, `--port` for live mode; demo config from YAML |
| `PYTHONPATH=. python scripts/tools/run_tools.py --tool SearchTool --args '{"query": "test"}'` | ✅ | `--chain`, `--init-args`, `--interactions`, `--list` |
| `PYTHONPATH=. python scripts/experiments/compare_experiments.py --contrast reflect_0_vs_reflect_1` | ✅ | Ablation comparison |
| `PYTHONPATH=. python scripts/evaluation/jev_smoke_test.py` | ⚠️ Manual | Requires `TYPESAFE_API_KEY` |
| `PYTHONPATH=. python scripts/llm_agent/smoke_real_llm.py --domain Video_Games --text "recommend games"` | ⚠️ Manual | Requires `LLM_BASE_URL`, `LLM_API_KEY` |
| `PYTHONPATH=. python scripts/eda_diagnostic/run_eda.py --domain Video_Games` | ✅ | `--sample` |
| `PYTHONPATH=. python scripts/eda_diagnostic/diagnose_splits.py --domain Video_Games --tag multi_domain` | ✅ | Split diagnostics |

### 0.15.3. Adding a New Component Benchmark

1. Create dataset: `package/evaluation/component/benchmarks/<name>_dataset.jsonl`
2. Create evaluator: `package/evaluation/component/benchmarks/<name>_benchmark.py` (subclass `ComponentEvaluator`)
3. Register in `package/evaluation/component/run_benchmark_cli.py:_get_evaluator()`
4. Add to `configs/eval/component_benchmarks.yaml:datasets` map
5. Add per-component config in `configs/eval/component_benchmarks.yaml:configs.<name>` if needed
6. Run: `PYTHONPATH=. python scripts/evaluation/run_component_benchmarks.py`

### 0.15.4. Adding a New Config

1. Create YAML in appropriate `configs/<category>/`
2. Define Pydantic schema in `package/config/schemas.py` (if new structure)
3. Use `load_config("category/file")` in code
4. Add test in `tests/config/`

### 0.15.5. Debugging Failed Runs

```bash
# Check trajectory file for errors
cat experiments/agent_eval/exp_NNN/trajectories.jsonl | jq 'select(.error != null)'

# View component benchmark unified report
cat experiments/agent_eval/component_benchmarks/unified_report_*.md

# Check pipeline logs
cat experiments/logs/<tag>/run_pipeline.log

# Verify tag manifest
PYTHONPATH=. python scripts/data_pipeline/verify_tag.py --tag <tag>
```---

## 0.16. Future Work (Updated with Current Status)

### 0.16.1. Priority 1: Unblock Real Evaluation

1. **Set `LLM_BASE_URL` / `LLM_API_KEY`** — Enable planner benchmark and real agent evaluation. **chưa có artifact xác nhận**
2. **Set `TYPESAFE_API_KEY`** — Enable real Jev grounding evaluation. **chưa có artifact xác nhận**
3. **Run retrieval recall experiments** — Quantify BM25 recall on real catalog. **chưa có artifact xác nhận**
4. **Fix `git_sha` population in reports** — Link results to exact code version. **chưa có artifact xác nhận**

### 0.16.2. Priority 2: Fix Agent Quality

5. **Improve planner tool selection** — `tool_selection_accuracy: 0.4904` (unified_report_20261110_210732.md:66); needs better prompt / few-shot / model. **chưa có artifact xác nhận**
6. **Improve planner argument correctness** — `argument_correctness: 0.3842` (unified_report_20261110_210732.md:67). **chưa có artifact xác nhận**
7. **Fix reflection effectiveness** — Quality threshold reflection untested in component benchmark; `reflect_quality_threshold` in config. **chưa có artifact xác nhận**
8. **Validate grounding with real answers** — Dummy answer limitation fixed; test with real LLM inference output. **chưa có artifact xác nhận**

### 0.16.3. Priority 3: Retrieval & Ranking

9. **Measure BM25 recall on real catalog** — Run candidate_recall experiments. **chưa có artifact xác nhận**
10. **Implement embedding-based retrieval** if BM25 recall insufficient. **chưa có artifact xác nhận**
11. **Vietnamese/English retrieval gap analysis** — Compare semantic vs. keyword on Vietnamese queries. **chưa có artifact xác nhận**

### 0.16.4. Priority 4: Operationalize Evaluation ✅ **COMPONENT BENCHMARKS DONE**

12. ✅ **Component benchmarks implemented** — 5 components (Memory, Planner, Grounding, Integration, Executor) with unified report (unified_report_20261110_210732.md)
13. ✅ **Multi-turn evaluation framework exists** — Benchmark runs on synthetic fixture corpus (unified_report_20261110_210732.md:147-190); metrics: `turn_success_rate: 1.0000`, `conversation_success_rate: 1.0000`, `context_retention_mean: 1.0000`
14. ✅ **Campaign runner works** — Campaign `campaign_001` executed 8/12 runs successfully; artifacts in `src/experiments/agent_eval/campaigns/campaign_001/` (campaign_001_summary.md)
15. **Complete Opik complementary integration** — Deploy Opik, add `@opik.track` decorators, import historical experiments. **chưa có artifact xác nhận**
16. **Fix integration latency measurement** — Ensure end-to-end execution time captured (current 0.0007s is contract-only). **chưa có artifact xác nhận**
17. **Populate `git_sha` in all reports** — Link results to exact code version. **chưa có artifact xác nhận**
18. **Add real-provider smoke tests** to CI (optional, gated). **chưa có artifact xác nhận**

### 0.16.5. Priority 5: Architectural Enhancements

19. **Implement embedding-based retrieval** if BM25 recall insufficient. **chưa có artifact xác nhận**
20. **Add BPR-MF to online serving** (currently evaluation only). **chưa có artifact xác nhận**
21. **Real multi-turn evaluation** with LLM (replace MockAgentRunner). **chưa có artifact xác nhận**
22. **Cross-domain recommendation** (currently per-domain corpus). **chưa có artifact xác nhận**---

### 0.16.6. Priority 6: Evaluation Integrity — Repository Audit Follow-ups (added 2026-11-15)

Items from the comprehensive repository audit + TD-13 / Section 5B investigations. `[INVESTIGATE]` = read-only analysis task producing a recommendation per item; `[CLEANUP]` = gated implementation task. Do NOT implement inside investigation tasks.

23. **[DONE] TD-13 — Incomplete evaluation metrics.** Resolved 2026-11-16 after R1–R3 had already landed per-path pool verdicts and stage-loss diagnostics. Decisions per metric:
    - `target_in_pool` (flat) — stays `None` **by design**: no single eligible item universe across SQL/Semantic/ItemCF paths. Added `target_in_any_path_pool` instead (existential verdict over all target×path pool entries: any True → True, all measurable False → False, else None) in `score_layer1_outcome.py`.
    - `target_reachable` — already real via `_extract_stage_diagnostics` (True if any target retrieved by any exercised path).
    - `target_in_pool_{sql,semantic,itemcf}`, `target_pool_detail`, `stage_lost`, `target_stage_detail`, `rank_in_pool` — real per-path/per-target diagnostics from R2/R3.
    - `query_hit_any_title_token` — **implemented** in `_extract_stage_diagnostics`: existential per-request verdict; union of `query_tokens` across ok SearchTool steps vs `tokenize_search_query(target title)`; aggregates in `summarize` (bool → rate). Measures lexical reachability of the BM25 path.
    - `_extract_retrieval_diagnostics` (layer3) — **removed**: fully dead after R3 (all its keys were overwritten by stage diagnostics or permanently None). `score_layer3_grounding` now emits only answer-status/grounding keys.
    - `_score_language` — **kept, documented**: ASCII-script heuristic (5/3), explicitly marked NOT language detection in module/function docstrings; official language quality is the Jev judge (`evaluate_product_reply_with_jev`).
    - `evolving_interest` — **False → pd.NA** (nullable boolean): unavailable ≠ "checked, none found". Logic still unimplemented; blocked on category time-series data (`acquire.py`).
    - `summarize.py` None-safety re-verified: `None` values are filtered before means; diagnostic keys remain in `_NON_NUMERIC_KEYS`; `target_in_any_path_pool` and `query_hit_any_title_token` intentionally aggregate as rates.
24. **[INVESTIGATE] Section 5B — Simulated inputs in real evaluation.** Document how simulated requests/queries are constructed, flagged, and reported; check for target leakage into "realistic" requests.
    - `package/evaluation/requests/build_requests.py` — requests synthesized from held-out data; trace `request.oracle` flag and `query_provenance` propagation into `run_agent_eval.py`, `trajectory/score_trajectory.py`, `ablation/_report.py` (`is_oracle`).
    - `package/evaluation/requests/filter_requests_by_scope.py` + `configs/agent/agent_eval.yaml:request_scope` — `realistic` | `oracle` | `all` semantics.
    - `scripts/evaluation/candidate_recall.py` + `configs/eval/candidate_recall.yaml` — `history` vs `category_oracle` query modes (`package/config/_schemas.py:14` `QUERY_MODES`).
    - Verify oracle-derived results are separated from realistic-proxy results in downstream reports (`experiments/**`, ablation `comparison.*`, `metrics.json`).
    - Check no held-out target info leaks into "realistic"/"similar"/"personalized" request construction (constraints must come from fit history only).
25. **[CLEANUP] Section 5B — Placeholder/demo-only output filtering.** Prevent placeholder, fabricated-demo, and dry-run outputs from being mistaken for genuine results. Gated actions to evaluate; do NOT delete legitimate test doubles, synthetic benchmark fixtures, independent oracle implementations (`compute_memory_oracle.py`, `oracle_fixture_knn.py`), or documented offline proxies.
    - `package/evaluation/reporting/_visualizations.py` — 6 chart functions emit "PLACEHOLDER — chart not implemented" Markdown stubs; implement or remove from official report paths.
    - `package/evaluation/component/link_component_to_e2e.py` + `create_traceback_tool.py` — emit `placeholder_not_computed` / `keyword_heuristic_placeholder`; require explicit opt-in via `scripts/evaluation/link_e2e_cli.py` and/or exclude `placeholder_*` statuses from official summaries.
    - `scripts/evaluation/generate_example_report.py` — hardcoded fabricated metrics; keep isolated (already labeled "must not be cited") or move under `scripts/demo/`.
    - `scripts/evaluation/opik_poc.py` — DRY-RUN simulated Opik with fixed placeholder scores; keep PoC labeling, ensure outputs can't enter eval summaries.
26. **[RESOLVED 2026-11-16] Evaluation metric integrity audit.** Full details in §0.17.20. Fixed: `exclusion_compliance` (structured request fields + real L2 computation), `cost_per_successful_request` (derived post-override in combiner), `error_taxonomy` `"no_error"` rename, `aggregate_metrics` hardening, L4 `n_steps`/`steps_ok_rate` gating, kind-aware `reflection_succeeded`, `memory_profile_usage` value-matching, include-all-verdicts summarize policy, new `diagnostics.pool_stage` aggregates. Deferred/open: `reachable_only_*@k` (reserved dead columns), `rank_in_pool` direction metadata, empty-bootstrap `(0,0,0)`, cosmetic report/progress labels. Verified: 458 eval tests + offline dry-run v2 (`dryrun_offline/`).
    - `campaign_001` artifacts still predate all of the above: funnel counts are stale fake-zeros, `rank_in_pool` all-0, no diagnostic columns; `campaign_result.json` comparisons hold only the 43-metric legacy summary. Thesis-citable diagnostic metrics require a re-run.
---

## 0.17. Evaluation System — Complete Reference (added 2026-11-16)

Deep reference for the entire evaluation surface: every `package/evaluation/` module (per-def), every eval script, the test-coverage map, and the known-issues register (§0.17.20). Companion to §0.8 (high-level) — this section is the authoritative inventory.

### 0.17.1. End-to-end pipeline map (`scripts/evaluation/run_agent_eval.py`)

Stages inside `main()`, in order. Everything after "score" is post-hoc and LLM-free:

| Stage | What happens | Artifacts |
|---|---|---|
| 1. Config+overlay | `load_config("agent/agent_eval")` etc.; `CONFIG_OVERLAY_PATH` deep-merges per-run overrides (campaign writes one per experiment) | — |
| 2. Data load | `get_data_paths` → splits (`load_splits`), fit/target (`select_fit_target`), user/item mappings, corpus (`ItemCorpus` sqlite or prebuilt), temporal `as_of` | — |
| 3. ItemKNN | fit fresh or reuse validated cache (`item_knn_reuse_cache` + `item_knn_dir`); `BaselineScorer`/`HybridScorer` per `agent/scoring.yaml` | cache under campaign dir when reused |
| 4. Tools+provenance | `build_tools` (dense leg optional via `eval/dense_retrieval.yaml`), `build_run_provenance` (prompt/tool-schema/git/limits hashes) | — |
| 5. LLM gate | `needs_llm = planner agents present OR (inference.mode=llm AND inference agents present)`; `build_llm_provider` + `health_check()` (real API ping) → `SystemExit` on failure. `agents=[baseline,type1]` + `mode=template` ⇒ **fully offline** | — |
| 6. Requests | `build_requests` (deterministic given seed) → `filter_requests_by_scope` (`realistic`/`oracle`/`all`) | `requests.jsonl` |
| 7. Trajectories | per request×agent with `applicable` filter (baseline needs `user_idx`; type1 only `kind=="similar"`; planners always); `--resume` reuses records matching `evaluation_protocol_hash` | `trajectories.jsonl` (appended live) |
| 8. ItemCF reachability | `_itemcf_reachable` (global) + `_itemcf_reachable_for_seeds` (per-trajectory seeds from logged SimilarTool args) | — |
| 9. Scoring | `score_trajectory` per trajectory → flat row (~90 cols) → `summarize(rows)` | `scored.jsonl`, `metrics.json` (`{k, summary, diagnostics}`) |
| 10. Multi-turn (opt-in) | `run_optional_multi_turn` → `multi_turn.json` or campaign `multi_turn/` dir; statuses: success/resumed/skipped_no_credentials/timeout/error/failed | `multi_turn.json` + status sidecar |
| 11. Jev (opt-in) | `run_optional_jev` → judges `answer_status=="ok"` trajectories → `jev_eval.jsonl`; `skipped_no_credentials` without `JEV_API_KEY`/`TYPESAFE_API_KEY`/`OPENROUTER_API_KEY` | `jev_eval.jsonl` |
| 12. Diagnostics (always) | `error_taxonomy` (trajectory copies with injected `kind`) + `reflection_diagnostics` (scored rows) → `diagnostics` block in metrics.json + `diagnostics.json` | `diagnostics.json` |
| 13. Reporting (always) | `build_report_results` → `report.md`, `report.csv`, `failures.md` (if any), `charts/*.svg`; try/except — render failure never sinks eval | `report.*`, `charts/` |
| 14. Save | `save_experiment` → `config.yaml`, `metrics.json`, `README.md`; copies trajectories/requests/scored/jev/diagnostics into `exp_dir` | whole `exp_NNN/` (or campaign `run_N/`) |

Campaign (`run_campaign.py` → `CampaignRunner`) wraps stage-per-experiment as a **subprocess** with a generated `config_overlay.yaml`, then adds: experiment comparisons (paired bootstrap + McNemar via `evaluation.statistics`), multi-turn aggregation, and post-run ablation contrasts.

### 0.17.2. Scored-row column catalog (`scored.jsonl`, ~90 cols)

Row = identity + L1–L5 + funnel + stage diagnostics. `None` = metric not defined for that agent/kind/trajectory (never a silent 0 — except where noted in §0.17.20).

| Producer | Columns |
|---|---|
| identity | `request_id`, `agent`, `kind`, `segment`, `oracle` (bool: request built from held-out targets) |
| L1 outcome | `n_recommended`; `precision@k`,`recall@k`,`hit_rate@k`,`ndcg@k`,`mrr@k`,`map@k` (k-formatted, e.g. `@10`); `seen_item_rate`; `seed_in_result`; `distinct_domains`; `distinct_main_categories` |
| L1 pool diagnostics | `target_in_pool` (**always None by design** — no single eligible universe); `target_in_any_path_pool`; `target_in_pool_{sql,semantic,itemcf}`; `target_pool_detail` (dict); `target_reachable`; `target_rank_detail`, `target_stage_detail` (dicts); `stage_lost` (`pool`/`retrieve`/`survived`/`final`/`rank_*`/`mixed`); `rank_in_pool`; `retrieved_by_{sql,semantic,itemcf}`; `query_hit_any_title_token` |
| L1 funnel | `candidate_generation_count`, `retrieved_count`, `filtered_count`, `ranked_count`; `reachable_only_{precision,recall,hit_rate,ndcg}@k` (**dead/deferred — see §0.17.20**) |
| L1 kind-gated | `category_coverage` (constrained/cold_text only) |
| L2 interaction | `task_success` (kind-specific v2); `constraint_satisfaction`, `price_unknown_rate` (constrained/cold_text only); `asked_clarification`; `exclusion_compliance` + `exclusion_compliance_detail` (exclusion kind, structured fields since fix — §0.17.20) |
| L3 grounding | `answer_status_{ok,ask_user,no_result,tool_error}`; `answer_grounded`, `answer_fallback` (only when `answer_status=="ok"`, else None) |
| L4 process | `plan_valid`, `plan_attempts`, `plan_truncated`, `n_steps`, `steps_ok_rate`, `invented_ids`, `reflections`, `first_attempt_ok`, `tool_selection_ok`, `args_valid_rate`, `price_arg_ok`, `category_arg_ok`, `used_ranker` (planner-only where gated); `itemcf_seed_correctness`, `memory_profile_retrieved`, `memory_profile_usage`, `semanticsearch_keyword_quality`, `tool_argument_correctness`, `component_failure_diagnosis`, `reflection_invoked`, `reflection_succeeded`, `component_states` (diagnostics; mostly planner-only) |
| L5 deployment | `prompt_tokens`, `completion_tokens`, `llm_latency_seconds`, `tool_latency_seconds`, `wall_seconds` (all agents where applicable); `inference_{attempts,prompt_tokens,completion_tokens,latency_seconds}` (answered trajectories only); `provider_error`; `sql_time_budget_hits`; `per_step_{tokens,latency,cost}` (lists); `cost_per_request`, `cost_per_successful_request` (derived in `score_trajectory` after final `task_success`), `cost_breakdown_by_component`; `latency_{mean,p50,p95,p99,std}` (per-trajectory step-latency distribution) |

`summarize(rows)` → `{agent: {kind: {segment|"all": {metric: mean}}}}` — means over **non-None** values only; `_NON_NUMERIC_KEYS` skips dict/list/str columns (incl. all `target_*_detail`, `stage_lost`, funnel counts, `category_coverage`, `reachable_only_*`); `_PERCENTILE_COLUMNS` adds `_p50`/`_p95` for latency/token columns. All other columns — bool verdicts (`target_in_pool*`, `target_reachable`, `retrieved_by_*`, `query_hit_any_title_token`, `target_in_any_path_pool`), `exclusion_compliance`, `rank_in_pool`, `n_steps`, … — **do** aggregate as 0/1 rates (or means) into `metrics.json.summary` → campaign comparisons (policy: include-all-verdicts, §0.17.20).

### 0.17.3. `trajectory/` — orchestration + aggregation

| Def | Signature essence | Purpose |
|---|---|---|
| `score_trajectory` | `(request, trajectory, *, item2id, corpus, k, seen_item_ids, id2item, itemcf_reachable, itemcf_reachable_request)` | Calls L1–L5 + `_extract_retrieval_funnel` + `_extract_stage_diagnostics`, merges into one flat row. Special override: `personalized` + planner without `MemoryTool` → `tool_selection_ok`/`task_success` = None (cannot honestly personalize). Failures score as zeros, not skipped samples. |
| `summarize` | `(rows)` | agent→kind→segment("all")→mean; skips `_ID_KEYS` + `_NON_NUMERIC_KEYS`; non-None filter; `_PERCENTILE_COLUMNS` → `_p50`/`_p95`. |

### 0.17.4. Scoring layers (per-def)

**`layer1_outcome/score_layer1_outcome.py`** — outcome + all retrieval diagnostics:

| Def | Purpose |
|---|---|
| `score_layer1_outcome` | Dedup recs → top-k; ranking metrics via `ranking_metrics_at_k` (only non-ambiguous kinds with targets, else None); pool verdicts via `_target_pool_detail`; funnel merge happens in `score_trajectory`, not here |
| `_extract_retrieval_funnel` | S0–S5 counts from step `data` payloads; returns `{}` (→ None columns) when any relevant step lacks a `data` dict — **unmeasurable ≠ 0** |
| `_target_pool_detail` | Per-target × per-path (`sql`/`semantic`/`itemcf`) pool membership; `None` = availability unknown |
| `_any_path_pool_verdict` / `_pool_path_verdict` | Existential aggregation: any True → True; all measurable False → False; else None |
| `_step_item_ids`, `_path_candidates`, `_search_query_tokens`, `_query_hit_title_verdict`, `_last_ranker` | Step-data extraction helpers for stage diagnostics |
| `_extract_stage_diagnostics` | Per-target stage-loss: `pool`→`retrieve`→`survived`/`final`/`rank_unscored`/`rank_excluded_seen`/`rank_topk`/`rank_input`; emits `target_reachable`, `stage_lost`, `rank_in_pool` (= min target rank), `retrieved_by_*`, `query_hit_any_title_token`, detail dicts |

**`layer2_interaction/score_layer2_interaction.py`** — single def `score_layer2_interaction(request, trajectory, *, corpus)`: kind-specific `task_success` v2 (ambiguous=asked; unanswerable=ask_user/no_result/grounded-empty; exclusion=plan+steps+recs **+ compliance check that is currently dead**; others=plan+steps+recs+constraint+answer ok&grounded for new trajectories). `constraint_satisfaction`/`price_unknown_rate` only for constrained/cold_text via `items_satisfying`/`items_without_price`.

**`layer3_grounding/score_layer3_grounding.py`** — single def: `answer_status_*` flags (None when trajectory has no answer — baseline/old records); `answer_grounded`/`answer_fallback` only for `ok`. Deterministic surface check (items mentioned + numbers), NOT semantic faithfulness — Jev covers that.

**`layer4_process/`** — `score_layer4_process(request, trajectory)` + `_helper._follows`/`check_tool_selection`: plan validity, step stats, tool selection vs `reference_groups` (from `_schema.REFERENCE_PLANS` filtered by `tools_available`), arg checks, and diagnostic columns (`itemcf_seed_correctness`, `memory_profile_*`, `semanticsearch_keyword_quality`, `tool_argument_correctness`, `component_failure_diagnosis`, `component_states`, `reflection_*`). See §0.17.20 for heuristic limitations.

**`layer5_deployment/score_layer5_deployment.py`** — single def: token/latency usage (planner `usage` vs answer `inference_usage`), `provider_error`, `sql_time_budget_hits` (via `check_time_budget_error`), per-step breakdowns, `cost_per_request`, `cost_breakdown_by_component`, per-trajectory latency distribution. `cost_per_successful_request` is derived in `score_trajectory` (needs final `task_success`, unavailable at L5).

Each layer has `_schema.py` with a `COLUMNS` tuple — a **subset** used for CLI summary printing (`SUMMARY_COLUMNS` in run_agent_eval); actual rows are wider (funnel/stage/diagnostic cols not listed there).

### 0.17.5. `diagnostics/` — always-on aggregations (wired into every run)

| Def | Input | Output | Notes |
|---|---|---|---|
| `error_taxonomy(trajectories)` | trajectory dicts (kind injected on copies by caller) | `{agent: {kind: {step_errors: {error_kind: n, "no_error": n_ok_steps}, plan_errors: {plan_invalid, provider_error}}}}` | `"no_error"` bucket = steps WITHOUT error (renamed from `"None"`, §0.17.20) |
| `reflection_diagnostics(rows)` | scored rows | `{agent: {kind: {n_first_failed, rescue_rate, mean_reflections, constraint_blind_spot_rate}}}` | Conditional means; `None` when unmeasurable (no first-failures, non-oracle kinds) |
| `pool_stage_diagnostics(rows)` | scored rows | `{agent: {kind: {n_rows, rates: {col: {rate, n}}, stage_lost_counts, rank_in_pool: {median, mean, n}}}}` | Added 2026-11-16; rates over measurable (non-None) rows only; `rank_in_pool` lower-is-better |

`failure_rates.py` was removed (duplicated `summarize` means). Output → `metrics.json["diagnostics"]` + `diagnostics.json`; campaign flattening reads only `summary` → never enters comparisons.

### 0.17.6. `reporting/` — real per-run reports (wired, always-on)

| Def | Purpose |
|---|---|
| `build_report_results(rows, trajectories, *, k, trajectory_path, multi_turn)` (`_adapter.py`) | Converts scored rows + trajectories → legacy `results` shape: `request_kinds` keyed `"agent/kind"` with recomputed mean/std/min/max/count (None excluded); `metric_values` (headline metrics → CI + latency chart); `latency_values`; `retrieval_funnel` (mean of funnel counts); `failures` (`task_success` falsy-not-None or `provider_error` → stage/cause/trace ref); `summary` scalars. **Does not fabricate** `layers`/`components` sections — generators skip absent keys |
| `_headline_keys`, `_metric_values`, `_group_stats` | Adapter internals |
| `generate_markdown_report(results, output_path, include_confidence_intervals, confidence_level)` | Executive summary + per-kind tables + 95% bootstrap CIs |
| `generate_csv_export(results, output_path)` | Flat CSV of request-kind metrics |
| `generate_failure_report(failures, output_path)` | Failure list w/ stage + trajectory error + trace ref |
| `generate_comparison_report(comparison, output_path)` | Two-experiment comparison (no current pipeline producer — campaign uses its own stats) |
| `_visualizations.py` | Dependency-free SVG: `_bar_chart`, `_heatmap`, `generate_layer_comparison_chart` (needs `layers` — absent for agent_eval), `generate_request_kind_heatmap`, `generate_retrieval_funnel_chart`, `generate_latency_distribution_chart`, `generate_multi_turn_performance_chart`, `generate_all_charts` |

Consumer warning in `__init__.py`: `generate_example_report.py` remains a **synthetic DO-NOT-CITE demo** (`experiments/agent_eval/example_report/`, gitignored, banner-stamped).

### 0.17.7. `judge/` — Jev post-hoc pass (wired, opt-in)

| Def | Purpose |
|---|---|
| `evaluate_trajectories_with_jev(trajectories, requests_by_id, corpus, *, max_requests, …)` | Judges trajectories with `answer_status=="ok"` only; gathers recommended-item metadata from corpus in recommendation order; returns one row per judged request → `jev_eval.jsonl` |
| `_items_for(corpus, item_ids)` | Corpus metadata rows in request order |
| `JevClient(api_key, model, base_url)` (`jev_client.py`) | TypeSafe AI System One wrapper (Noul/Score questions); env fallback `JEV_API_KEY`→`TYPESAFE_API_KEY`→`OPENROUTER_API_KEY` |
| `jev_credentials_configured()` | Credential probe for gating (`skipped_no_credentials`) |

Config: `agent_eval.jev.{enabled,max_requests}`; campaign per-experiment `agent_config.jev` (bool|dict) via `_normalize_jev_param`.

### 0.17.8. `requests/` — request construction

| Def | Purpose |
|---|---|
| `build_requests(*, seg_of, target_by_user, last_item_of, id2user, id2item, item2id, corpus, per_segment, n_ambiguous, language, k, price_slack, price_round_to, rng)` | Simulated requests from held-out data (no real query log): personalized (fit history), similar (seed=most recent fit item), ambiguous (no targets), unanswerable (impossible constraints), constrained/cold_text/exclusion (**oracle** — constraints from held-out items). Deterministic given seed |
| `filter_requests_by_scope(requests, scope)` | `realistic` = drop `request.oracle`; `oracle` = only oracle; `all` = everything |
| `reference_groups(kind, available_tools)` | Reference-plan tool groups for L4 `tool_selection_ok`, filtered to tools the agent actually has |
| `AgentRequest` (`_dataclass`) | `request_id, kind, segment, text, user_id, user_idx, seed_item_id, targets[item_idx], price_max, category, excluded_item_ids, excluded_categories, oracle` — structured exclusion fields added 2026-11-16 (§0.17.20); schema change invalidates pre-change resume hashes |
| `_helper._price_of/_deepest_category/items_satisfying/items_without_price` | Corpus lookups for constrained-kind scoring |

### 0.17.9. `statistics/` — campaign-level stats (`_bootstrap.py`)

| Def | Purpose | Caveat |
|---|---|---|
| `bootstrap_confidence_interval(values, confidence_level, n_bootstrap, random_seed)` | Percentile bootstrap CI → `(mean, lo, hi)`; `(0,0,0)` on empty | fake-zero on empty input |
| `paired_bootstrap_difference(values_a, values_b, …)` | Paired bootstrap of B−A → `(mean_diff, lo, hi, p_value)`; p = tail proportion | — |
| `aggregate_metrics(metrics_list)` | mean/std/min/max/count per key | Skips missing keys AND non-numeric/`None` values (hardened 2026-11-16); **no production caller** — campaign stats go through `summarize`/bootstrap paths |
| `compute_percentiles(values, percentiles)` | p50/p95/p99 dict | — |
| `significance_test(values_a, values_b, test_type, alpha)` | paired/independent significance | — |

Campaign `_compare_experiments` uses `bootstrap_confidence_interval` + `paired_bootstrap_difference` driven by `statistical_settings` in campaign.yaml. Ablation has its own `_statistics.py` (bootstrap_ci + `mcnemar_test` + `wilson_interval`) — intentionally separate.

### 0.17.10. `provenance/build_run_provenance.py`

`_sha256`, `_json_sha256`, `_git_info` → `build_run_provenance(planner_tools, memory_tools)` — hashes of planner/memory prompts + tool schemas + git sha/dirty + limits; stored in `config.yaml`/experiment metadata for reproducibility.

### 0.17.11. `ablation/` — case-level paired comparison (shared runner)

| Def | Purpose |
|---|---|
| `run_ablation_contrasts(*, limits, groups, contrasts, output_dir)` (`_runner.py`) | Executes every contrast → per-contrast `report.md`/`comparison.json`/`comparison.csv`/`disagreements.jsonl`; per-contrast errors don't sink others; missing `scored.jsonl`/`config.yaml` = error status, not crash. Used by `compare_experiments.py` (paths) AND `CampaignRunner._run_ablation` (experiment names → run dirs) |
| `load_scored_data/load_config_data/load_group_data/load_group_data_dirs` (`_loader.py`) | Read `scored.jsonl`/`config.yaml` per exp dir; `check_compatibility` (seed/per_segment/eval_on/policy/protocol match); `validate_contrast_config` |
| `pair_by_request_id`, `average_across_runs`, `compute_metric_diff`, `compute_binary_disagreement`, `compare_two_groups`, `find_disagreements` (`_compare.py`) | Pair scored rows by `request_id` across runs/agents; bootstrap CI per metric; McNemar disagreements |
| `pairwise_report`, `render_pairwise_markdown` (`_pairwise.py`) | **None-aware** pairwise analysis — drops None pairs explicitly (vs `compare_experiments` treating None≈absent); used by `scripts/experiments/pairwise_ablation.py` |
| `bootstrap_ci`, `mcnemar_test`, `wilson_interval` (`_statistics.py`) | Stats primitives; Wilson returns None at n=0 |
| `render_markdown_report`, `write_csv`, `write_json`, `write_disagreements` (`_report.py`) | Artifact writers |
| `AblationLimits`, `get_ablation_limits()` (`_limits.py`) | Frozen config from `configs/agent/ablation.yaml`: `bootstrap_resamples`, `confidence`, `min_n_warn`, `seed`, `metrics`, `groups`, `contrasts`, `output_subdir` (validated >0/in-range) |

### 0.17.12. `campaign/` — experiment orchestration

| Def | Purpose |
|---|---|
| `ExperimentConfig` / `CampaignConfig` / `ExperimentRun` / `CampaignResult` (`_schema.py`, dataclasses) | `CampaignConfig`: `campaign_id, description, dataset, parameter_grid, experiments, evaluation_config, output_dir, comparison_pairs, statistical_settings, default_agents, agent_config_defaults, allow_missing_corpus_sources, experiment_timeout_seconds, multi_turn(never/once/all), ablation{contrasts}`; `expand_parameter_grid`, `compute_hash`, yaml/json roundtrip |
| `CampaignRunner.run_campaign(only)` | `_preflight_llm` first (per-experiment needs_llm rule; real provider ping once, `CAMPAIGN_SKIP_LLM_PREFLIGHT=1` bypass for tests) → select experiments (`--only` grid positions/ids, merge-not-overwrite) → per experiment: build overlay → subprocess `run_agent_eval.py` → parse `saved ->` dir → load `metrics.json.summary` → flatten `{agent}_{kind}_{metric}` (numeric only, `n` skipped) → comparisons → multi_turn aggregation → ablation contrasts → `campaign_result.json` + checkpoint |
| `_run_experiment` | Subprocess w/ timeout; writes `config_overlay.yaml` first (reflects config even on early failure) |
| `_build_config_overlay` | Maps `agent_config` keys → overlay fragments: `inference_mode`→`agent/inference`, `reflect_rounds`→`agent/agent`, `exclude_tools`, `jev`/`multi_turn` normalized, `random_seed`→`eval/baselines.seed`, campaign ItemKNN cache→`path/data_paths.item_knn_dir` + `item_knn_reuse_cache`. Campaign-level `agent_config_defaults` merge under every experiment's agent_config (experiment keys win) — campaign.yaml uses it for `jev: true` always-on |
| `_normalize_multi_turn_param` / `_normalize_jev_param` | bool→`{enabled:true}`; dict passthrough; explicit `{enabled:false}` written for grid isolation |
| `_multi_turn_plans` / `_multi_turn_run_dir` / `_run_multi_turn_fragment` / `_collect_multi_turn_result` | Policy never/once/all resolution; per-run multi_turn artifact status into `campaign_result.json["multi_turn"]` (coverage only — never in comparisons) |
| `_run_ablation` | Resolves contrast `[agent, experiment_name]` pairs → successful `run_N` dirs → `run_ablation_contrasts` → `<campaign>/ablation/<contrast>/`; subset merges recompute it over merged runs |
| `_merge_subset_result` | Merges `--only` runs into previous `campaign_result.json` (backup first): skipped runs kept verbatim, **comparisons + ablation recomputed over merged runs** (auto-gen pairs resolved over the full grid), summary/multi_turn regenerated |
| `_run_comparisons` / `_compare_experiments` / `_average_metrics` / `_generate_summary` | comparison_pairs → per-metric paired bootstrap CI + McNemar on repeated runs; averages across `repetition_count` |
| `_load_experiment_metrics` | Reads ONLY `metrics.json["summary"]` → flat `{agent}_{kind}_{metric}` means — diagnostics/reporting blocks cannot leak into comparisons |
| `CheckpointManager` | `save/load/clear_checkpoint` for crash recovery |

### 0.17.13. `multi_turn/` — conversation evaluation (opt-in, real-LLM)

| Def | Purpose |
|---|---|
| `MultiTurnEvaluator` (`multi_turn_evaluator.py`) | Per-turn scoring + conversation aggregation. Turn metrics: `turn_success`, `item_match_rate`, `exclusion_compliance` (**real impl lives here**, not trajectory L2), `tool_call_match_rate`, `no_result_compliance`, `clarification_compliance`, `reference_correctness`, `context_retention`, token usage. Conversation: `turn_success_rate`, `conversation_success`, `avg_item_match_rate`, aggregated compliance means |
| `_score_turn`, `_tool_call_match_rate`, `_arg_contains`, `_resolve_session_value` (`$S.<path>` refs), `_update_session`, `_calculate_conversation_metrics`, `_aggregate_metrics` | Turn/conversation internals |
| `RealAgentRunner` (`_agent_runner.py`) | PlanExecutor+Session per turn; `resolved_config()` echoes effective config; requires LLM |
| `run_multi_turn_eval` / `run_multi_turn_for_eval` / `extract_multi_turn_metrics` / `_write_status` / `_llm_configured` (`_eval_step.py`) | Gate used by run_agent_eval/campaign; statuses success/resumed/skipped_no_credentials/timeout/error/failed; `extract_multi_turn_metrics` pulls report-worthy scalars (never comparisons) |
| `_run.run_multi_turn_cli`, `load_conversations` | CLI + JSONL loader (`conversations.jsonl`, 13 convs incl. negative cases) |
| `_reporting.generate_markdown_report/generate_csv_export/generate_failure_report` | Multi-turn reports |
| `_schema` | `TurnInput`, `TurnResult`, `Conversation`, `ConversationResult`, `ConversationSummary` (all JSON-roundtrippable) |

### 0.17.14. `product_reply/` — answer evaluators (two implementations)

| Module | Role |
|---|---|
| `evaluate_product_reply.py` | Deterministic heuristic: `_extract_claims` → per-claim `_evaluate_claim` (price/rating/review/store/category support vs item fields + `_supported_by_title`) → `_check_items_in_order` → `_score_communication` (relevance/clarity/`_score_language` ASCII-heuristic/honesty, 1–5) → `_generate_summary`. CLI-only, NOT in agent_eval |
| `evaluate_product_reply_with_jev.py` | Same claim pipeline but `_evaluate_faithfulness_with_jev` (Noul questions per claim) + `_evaluate_communication_with_jev` (Score questions). Consumers: component `grounding` benchmark + `judge/evaluate_trajectories_with_jev` |

### 0.17.15. `component/` — component benchmarks (separate pipeline)

Framework: `_schema` (`BenchmarkCase/Result/Summary/RegressionReport`), `_loader` (JSONL load/save/tag+metadata filters), `_evaluator.ComponentEvaluator` (template: `run_component`→`score_component`→`run_case`→`run_benchmark`→aggregate metrics/latency/tags + `evaluate_thresholds` quality gate), `_regression` (`compare_benchmarks` → improved/regressed/neutral), `_run_all` (`run_all_benchmarks` → per-component CLI subprocesses → `unified_report_*.json/.md`; `_jev_configured`/`_llm_configured` gating; multi_turn step; `skipped_no_credentials`/`skipped_backlog` visible-not-failed), `run_benchmark_cli` (provenance: secret-scrubbed config hash + dataset sha256 + provider/judge info + evidence kinds), `run_regression_cli`, `run.py` dispatcher.

Benchmarks (`benchmarks/`): `memory_correctness_evaluator` (MemoryTool vs independent `compute_memory_oracle` + `leakage_probe` detector), `planner_benchmark` (`PlannerBenchmark` + `_step_error` schema validation + `_token_f1` clarification scoring), `executor_benchmark` (`ExecutorBenchmark` — real PlanExecutor._execute over fixture tools + per-step output assertions), `grounding_benchmark` (`GroundingBenchmark` — Jev claim-level; `ScriptedJudge` fake for tests; provider errors fail cases, never fake scores), `integration_benchmark` (`IntegrationBenchmark` — executor→inference boundary, `presented_ids`/`item_fields` metrics), `build_cases`/`render` (memory dataset gen), `analyze`/`analyze_metric`/`collect`/`default_metrics`/`memory_utility`/`render_markdown`/`scope_of` (paired multi-run memory-utility analysis — clear_effect verdicts require sufficient pairs+runs else inconclusive), fixtures (`create_test_*` synthetic corpus/interactions/mappings/meta), misc helpers (`get_interactions_without_rating`, `leakage_probe`, `week47` cases in datasets).

Helpers: `create_traceback_tool` (failure→component attribution; emits `placeholder_not_computed`/`keyword_heuristic_placeholder` statuses — gated opt-in), `link_component_to_e2e` (component↔e2e correlation, `_pearson`), `get_git_sha`.

### 0.17.16. `recommender/` — offline recommender evaluation (separate pipeline)

| Subpackage | Contents |
|---|---|
| `metrics/ranking/` | `precision_at_k`, `recall_at_k`, `hit_rate_at_k`, `ndcg_at_k` (binary gain), `mrr_at_k`, `average_precision_at_k` (MAP), `ranking_metrics_at_k` (validated batch entry — used by trajectory L1) |
| `metrics/retrieval/` | `candidate_retrieval_metrics` (dedup/pad candidate lists → retrieval quality/reach), `item_familiarity_metrics` (breakdown by target-in-fit) |
| `core/` | `evaluate_recommender` (model×exclude×target×ks×segments), `evaluate_ranking` (macro-avg over users w/ held-out), `evaluation_protocol` (provenance dict), `_dataclass.EvaluationResult.to_metrics`, `_helper.assign_segments`/`_git_commit` |
| `config/` | `parameter_grid` (cartesian expand), `merge_model_params`, `segment_users_by_history` (cold/sparse/warm) |
| `experiment/` | `save_experiment` (`_source_fingerprint` = hash of src/package+src/configs, env versions, dataset info, README), `next_experiment_dir` (`exp_NNN` allocator — shared with agent_eval), `RankingRunStore`/`RankingStreamSummary` (streaming ranking-eval storage) |
| `analysis/` | Read-only diagnostics ported for offline use: `diagnose_hit_losses`, `retrieval_loss_breakdown`, `classify_cf_link`, `candidate_policy_order`, `recent_priority_order`, `policy_chain_compare`, `cohort_policy_for_paths`, `confirmation_cohort`, `core_inputs`, `global_core_pairs`, `build_core_model`, `history_title_query`, `outside_core_content_retriever` — **no target labels enter policies** |
| `utils/` | `sha256_file`, `latency_summary`, `hardware_info`, `normalize_query_text`, `stage_progress` |

### 0.17.17. `package/evaluation/_schema.py` — fixed contracts

`KINDS`, `KIND_SEGMENTS`, `ORACLE_KINDS=("constrained","cold_text","exclusion")`, `PLANNER_AGENTS`, `INFERENCE_AGENTS=("type1","planner","planner_memory")`, `ANSWER_STATUSES`, `AGENTS`, `REFERENCE_PLANS` (per-kind expected tool groups for L4), `SUMMARY_COLUMNS` (k-formatted print columns), reference-plans lazy loader (`get_reference_plans`, cache invalidated on config/overlay change).

### 0.17.18. Scripts reference

**`scripts/evaluation/`** (34 files):

| Script | Role | Pipeline? |
|---|---|---|
| `run_agent_eval.py` | Main trajectory eval (see §0.17.1) | ✅ core |
| `run_campaign.py` | Campaign CLI → `CampaignRunner` | ✅ core |
| `run_component_benchmarks.py` | Thin wrapper → `component.run_all_benchmarks` + unified report | separate pipeline |
| `compare_experiments.py` *(scripts/experiments/)* | Ablation contrasts over exp dirs via shared `run_ablation_contrasts` | post-hoc manual |
| `pairwise_ablation.py` *(scripts/experiments/)* | None-aware pairwise via `_pairwise.pairwise_report` | post-hoc manual |
| `evaluate_product_reply.py` | Heuristic reply CLI (`--input-file` JSONL) | manual |
| `evaluate_with_jev.py` | Generic Jev evaluator for `{request,items,answer}` JSONL | manual escape hatch |
| `jev_smoke_test.py` | Jev connectivity + 1 real judgment (`configs/eval/judge.yaml`) | dev tool |
| `jev_negative_control.py` | Judge discrimination check w/ known-verdict fabricated cases (manual, needs key) | dev tool |
| `generate_example_report.py` | **SYNTHETIC DEMO — DO NOT CITE**; stamps banner + README into `example_report/` | demo only |
| `link_e2e_cli.py` | Wrapper → `link_component_to_e2e` + `create_traceback_tool` on an exp dir | manual opt-in |
| `memory_utility_analysis.py` | Wrapper → `benchmarks.memory_utility` (config-driven) | manual analysis |
| `build_memory_correctness_dataset.py` | Regenerate/check memory dataset (`--check` drift gate) | dataset tooling |
| `build_semantic_embeddings.py` | Standalone encoder pin + resumable embedding build (separate env) | data tooling |
| `prepare_semantic_candidate_cohort.py` | Freeze sparse validation cohort + one-seed CF lists | data tooling |
| `semantic_candidate_preflight.py` / `semantic_candidate_eval.py` | Read-only semantic pilot readiness / candidate eval | manual |
| `candidate_recall.py` | Do retrieval tools surface held-out items (history vs category_oracle modes) | offline eval |
| `ranking_eval.py` | Fixed-candidate ranking eval for deterministic tools | offline eval |
| `tune_item_knn_hybrid.py` | Tune CF/popularity blend on disjoint validation cohorts (never test) | offline tuning |
| `full_data_preflight.py` | Read-only readiness check (splits/mappings/corpus/KNN/semantic) → JSON | preflight |
| `diagnose_hit_losses.py` | CLI → `analysis.diagnose_hit_losses` on saved records | manual analysis |
| `retrieval_loss_diagnostic.py` | Read-only target/fit availability + source/merge loss | manual analysis |
| `analyze_ranking_bottlenecks.py` | Retrieval loss / ranking headroom / source fusion on saved candidates | manual analysis |
| `policy_chain_eval.py` | Frozen/fresh policy+fetch comparison, no labels to callbacks | manual analysis |
| `outside_core_content_probe.py` | History-title BM25 probe on outside-core targets (validation only) | manual analysis |
| `benchmark_categories_any.py` | SearchTool `categories_any`+FTS perf / EXPLAIN QUERY PLAN benchmark | perf tooling |
| `sparse_*.py` (6 scripts: `sparse_content_replay`, `sparse_data_diagnostic`, `sparse_guard_replay`, `sparse_ranking_replay`, `sparse_retrieval_probe`, `sparse_seed_eval`) | Fixed-sample read-only sparse-cohort diagnostics/replays — no refit, no LLM, no production changes | manual analysis |

**Adjacent eval-relevant scripts**: `scripts/demo/run_demo.py` (Gradio UI, inference-only — **no eval code**), `scripts/demo/demo_full_agent.py` (5-tool PlanExecutor demo), `scripts/llm_agent/smoke_real_llm.py` (PlanExecutor+tools on synthetic fixture, real LLM), `scripts/tools/check_llm_provider.py`, `scripts/tools/run_tools.py` (tools on real stage-3 data), `scripts/eda_diagnostic/` (`diagnose_splits` — why recall@10≡0; `oracle_fixture_knn` — independent KNN oracle for fixture datasets; `analyze_campaign_001_planner_errors`/`analyze_reflection_campaign_001` — read-only campaign_001 trajectory analyses; `run_eda`).

### 0.17.19. `tests/evaluation/` coverage map

| Dir | Files (tests) | Covers |
|---|---|---|
| `agent/` | `test_agent_eval` (60), `test_eval_integration` (19), `test_behavior_snapshot` (2), `test_config_resume_integration` (4), `test_reference_plans_config` (4), `test_scorer_yaml_cli` (1), `test_type1_audit` (1) | Requests/build/scope/oracle-flag/structured-exclusions, scoring incl. funnel None-vs-empty + step-data + exclusion compliance, memory-usage detection, summarize verdict policy, inference columns + resume identity, reference-plan config cache, scorer yaml, type1 step fidelity, behavior snapshot |
| `ablation/` | `test_compare` (7), `test_loader` (14), `test_pairwise` (7), `test_report` (6), `test_runner` (3), `test_statistics` (6), `test_limits` (1), `test_integration` (1) | Pairing/averaging/CIs, loader+compatibility gates, None-aware pairwise, report writers, shared runner error isolation, stats primitives |
| `campaign/` | `test_campaign` (29), `test_only_subset` (5), `test_ablation_wiring` (6), `test_multi_turn_wiring` (class-based) | Schema roundtrips, grid expansion, overlay mapping, stdout metric loading, comparisons, subset merge, ablation/jev/multi_turn wiring |
| `component/` | `test_loader` (10), `test_regression` (9), `test_thresholds` (10), `test_run_all` (13), `test_run_all_provenance` (4), `test_cli_reproducibility` (5), `test_provenance` (5), `test_memory_correctness` (11), `test_memory_utility` (10), `conftest` | Loader/filters, regression verdicts, threshold gate, run_all no-fake-PASS + credential visibility, provenance hashing, oracle correctness, paired memory-utility stats |
| `component/benchmarks/` | `test_controlled_tools` (4), `test_executor_dataset` (8), `test_grounding_benchmark` (1), `test_grounding_dataset` (7), `test_grounding_phase1` (6), `test_integration_dataset` (10), `test_memory_oracle` (3), `test_planner_dataset` (12), `test_week47_cases` (6), `fakes/` | Dataset lints, oracle independence, judge-error honesty, controlled-tool contracts, week-47 regression cases |
| `diagnostics/` | `test_diagnostics` (9) | error_taxonomy grouping/plan errors/`no_error`, reflection rescue/blind-spot/None rates, pool_stage rates/distributions/rank |
| `judge/` | `test_trajectories_with_jev` (5) | Eligibility (`answer_status==ok`), corpus context, `max_requests` cap, credential gating |
| `multi_turn/` | `test_evaluator` (8), `test_eval_step` (class-based), `test_dataset_and_evaluator_fixes` (15), `test_negative_expectations` (10), `test_reporting_and_loader` (8), `test_summary_turn_counts` (9), `test_with_session` (8) | Schemas, turn/conversation metrics, expect_* flags, session isolation/retention, reporting, honest p95/failed counts, eval-step gating |
| `recommender/` | `test_source_fingerprint` (4) | Fingerprint covers src/package+src/configs |
| `reporting/` | `test_adapter` (6) | agent/kind keys, None-exclusion, failures, generator acceptance |
| `stats/` | `test_bootstrap` (12) | CI/diff/aggregate/percentiles/significance incl. edge cases |
| root | `test_jev_reliability` (class-based), `test_judge_error_handling` (5) | Jev provider fake, judge errors never scored as unsupported |

### 0.17.20. Known issues & ambiguous-metric register (audit 2026-11-16, fixes applied same day)

Confirmed by code review + offline dry-run (`agents=[baseline,type1]`, `inference.mode=template` → `experiments/agent_eval/dryrun_offline/`). Backlog item 26. **Status column: FIXED = implemented + tested 2026-11-16; DEFERRED = consciously postponed; OPEN = still unresolved.**

**Dead/broken metrics**

| Metric | Status | Detail |
|---|---|---|
| `exclusion_compliance` | **FIXED** | `AgentRequest` gained `excluded_item_ids`/`excluded_categories` (defaults `[]`, `build_requests` populates from held-out exclude item + deepest category). L2 computes compliance = 1 − violating/total; violation = item_id match OR `item_categories` path contains an excluded category node. `exclusion_compliance_detail` = sorted violating ids. `task_success` for exclusion requires `== 1.0` when measurable. Schema change → pre-2026-11-16 resume hashes invalid (accepted; campaign_001 stale anyway). Real impl also exists in `multi_turn_evaluator` (unchanged) |
| `reachable_only_{precision,recall,hit_rate,ndcg}@k` | **DEFERRED** | Still set `None` at layer1, never computed; literal `@k` never formatted. Kept as reserved columns; implement or remove in a later pass |
| `exclusion_compliance_detail` | **FIXED** | Now has a real producer (L2, exclusion kind) |
| `cost_per_successful_request` | **FIXED** | L5 emits `cost_per_request` only; `score_trajectory` derives `cost_per_successful_request = cost_per_request if final task_success else None`, computed AFTER the personalized planner-override so `task_success=None` rows stay `None` |

**Ambiguous semantics (documented but easy to misread)**

| Metric | Status | Issue |
|---|---|---|
| `error_taxonomy` `step_errors` | **FIXED** | `"None"` bucket renamed `"no_error"` — counts steps without `error_kind` |
| `memory_profile_usage` | **IMPROVED (heuristic)** | Now detects `$N.path` refs **nested anywhere in args** (was top-level strings only — a real miss) plus value-matching: memory `top_categories`/`love_categories` ∩ `filters.categories_*`, `price_max` ≈ `price_range.max`, category substring in `query`, `loved/recent_items` ∩ `SimilarTool.items`. Still heuristic — coincidental matches can false-positive; documented in code. `usage` stays `None` when no MemoryTool step ran (`not_retrieved` label removed as dead code) |
| `args_valid_rate` vs `tool_argument_correctness` | **DOCUMENTED** | Kept separate: `args_valid_rate` = share of ALL steps without pre-call errors; `tool_argument_correctness` = share of schema-scored steps ok (`unknown_tool`/`invented_id` excluded from denominator). Distinction now commented in code |
| `reflection_succeeded` | **FIXED** | Kind-aware: `ambiguous` → success = asked + no steps; `unanswerable` → success = `ask_user`/`no_result`/grounded-ok-no-recs (legacy trajectories without `answer_status` → steps_ok + no recs); other kinds → unchanged (steps_ok + has recs) |
| `plan_valid`, `steps_ok_rate`, `n_steps` gating | **FIXED (partial)** | `n_steps` + `steps_ok_rate` now both compute whenever `steps` exist (type1 gets `n_steps`); `plan_*`/`invented_ids`/`reflections`/`first_attempt_ok` stay planner-gated. `plan_valid=True` for baseline still means "no error" — documented semantics, not changed |
| `rank_in_pool` in campaign comparisons | **OPEN (interpretation)** | Mean of per-row min-target-rank; lower-is-better. Now also in `diagnostics.pool_stage.rank_in_pool` (median/mean/n). No direction metadata in flat comparisons — cite carefully |
| `cost_per_request`/`cost_*` | **OPEN (context)** | Step `cost` fields rarely populated → 0.0 under template inference; honest but needs inference-mode context when cited |
| `statistics.aggregate_metrics` | **FIXED + CORRECTED CLAIM** | Original audit claim (`m.get(key,0)` fake-zero) was **inaccurate** — code already filtered `if key in m`. Hardened anyway: skips `None`/non-numeric values; `count` = runs that actually reported the metric. Note: function has **no production caller** |
| `bootstrap_confidence_interval([])` | **OPEN** | Returns `(0,0,0)` on empty input |
| summarize `_NON_NUMERIC_KEYS` split | **FIXED (policy: include-all-verdicts)** | `target_in_pool`, `target_in_pool_{sql,semantic,itemcf}`, `target_reachable`, `exclusion_compliance` removed from skip-list → aggregate as rates into summary → campaign comparisons. Still excluded: detail dicts, `stage_lost` (str), funnel counts, `category_coverage`, `reachable_only_*`. All-None columns absent from summary (unmeasurable ≠ 0) |
| pool/stage aggregate diagnostics | **FIXED** | New `diagnostics.pool_stage_diagnostics(rows)` → per agent×kind rates (all pool verdicts + `retrieved_by_*` + `query_hit_any_title_token`, each with measurable `n`), `stage_lost_counts`, `rank_in_pool` median/mean → `diagnostics.json` + `metrics.json["diagnostics"]` |
| report `requests` count | **OPEN (cosmetic)** | Adapter counts unique request_ids present in scored rows (requests with no applicable agent are invisible) |
| run progress denominator | **OPEN (cosmetic)** | `total = requests × agents` counts inapplicable agent-request pairs |

**Stale artifacts**

- `experiments/agent_eval/campaigns/campaign_001/**` scored/metrics predate TD-13 + step-`data` persistence: funnel counts are legacy fake-zeros, `rank_in_pool` all-0, zero diagnostic columns; `campaign_result.json` comparisons = 43-metric legacy summary only. **Any thesis number from campaign_001 covers only legacy metrics — diagnostic metrics (funnel/pool/stage/Jev) require a fresh campaign run.**

**Verified working (dry-run 2026-11-16)**

- Offline path: `agents=[baseline,type1]` + `inference.mode=template` needs no LLM; full chain produced real funnel counts (20→10), per-path pool verdicts, `stage_lost`, `diagnostics.json`, `report.md/.csv`, SVG charts.
- None-conventions hold: unexercised paths → `retrieved_by_*`=None; missing step data → funnel=None (post-fix); unmeasurable conditional rates → None.
- Wiring: diagnostics/reporting always-on; Jev/multi_turn/ablation opt-in and credential/policy-gated; campaign comparisons read `summary` only.

---

## 0.18. Glossary of Important Components and Terms

| Term | Definition |
|------|------------|
| **ItemCorpus** | Read-only SQLite database (FTS5 + BM25) storing item metadata. Built once, locked with `PRAGMA query_only=ON` and authoriser. Path: `src/package/corpus/` |
| **CandidateScorer** | Protocol for scoring candidate items for a user. Implemented by `BaselineScorer` (popularity + ItemKNN). Path: `src/package/tools/scoring/` |
| **PlanExecutor** | LLM-based agent: writes JSON plan → executes steps → optional reflection. Main planner agent. Path: `src/package/agents/plan_executor.py` |
| **Type1Agent** | Fixed-plan agent (no LLM): retrieve → rank → fetch. Used for baseline comparisons. Path: `src/package/agents/type1_agent.py` |
| **$N.path** | Reference syntax in planner: `$1.candidates`, `$2.ranked[0].item_id`, etc. Resolved at execution. |
| **MemoryTool** | Read-only user profile from interaction history (categories, price range, love/hate, recent items). Path: `src/package/memory/` |
| **Jev (TypeSafe AI)** | LLM-as-judge service for faithfulness (claim support) and communication quality (1-5 scale). Integrated via `JevProvider` at `src/package/api/jev_provider.py` |
| **Grounding** | Validation that answer only mentions items from `recommended` list, with correct numbers. |
| **Retrieval Funnel** | S0(target in pool)→S1(candidate gen)→S2(retrieval)→S3(filtering)→S4(ranking)→S5(final inclusion). |
| **Oracle Request Kinds** | `constrained`, `cold_text`, `exclusion` — use held-out target categories/prices/exclusions. Upper bound, not real queries. |
| **CONFIG_OVERLAY_PATH** | Env var for per-experiment config overrides (used by campaign runner). |
| **Run Tag** | Identifier for artifact directories (from `run_tag.yaml`, default `multi_domain`). |
| **Provenance** | Artifact tracking: file_hash, mapping_hash, fit_provenance, git_sha, config hash. Path: `src/package/evaluation/provenance/` |
| **ScriptedLLM** | Test double in `tests/agents/fakes/scripted_llm.py`: returns pre-scripted responses for testing. |
| **ScriptedJudge** | Test double implemented inline in `package/evaluation/component/benchmarks/grounding_benchmark.py`: returns pre-scripted Jev-like judgments. |
| **Fake*Tool** | Test doubles in `tests/agents/fakes/fake_tools.py`: deterministic fake tools for benchmarks. |
| **Campaign** | Orchestrated experiment runner managing grid experiments with per-experiment artifacts. Path: `src/package/evaluation/campaign/` |---

## 0.19. Document Provenance

| Field | Value |
|-------|-------|
| **Document** | `src/Project repository reading 29.10.md` (updated in place) |
| **Update date** | 2026-11-16 (added §0.17 Evaluation System Complete Reference, backlog item 26, §0.8/§0.18 fixes) |
| **Branch** | `tools-building` (evidence: `git rev-parse --abbrev-ref HEAD`) |
| **Commit** | `880bf5c` ("0749_1110") (evidence: `git log --oneline -1`) |
| **Working tree** | ~40 modified + ~70 untracked (evidence: `git status --short` → 112 lines; uncommitted evaluation work per §0.1.3) |
| **Key evidence sources** | Git commands (branch, log, status), pytest collection output, directory enumeration (Get-ChildItem), git log for phase history |
| **Unresolved evidence** | `resource/` data (missing), real LLM/Jev evaluation pending (planner baseline, −Rank arm), planner fixes not yet applied, final ablation numbers pending |---

**End of Repository Reading**
