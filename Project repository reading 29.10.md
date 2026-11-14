---
created: 2026-09-27-15:07
updated: 2026-11-14-14:00
viewed: 2026-11-14-14:00
branch: tools-building
commit: 880bf5c
---
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
| **Campaign resume** | `run_campaign.py --only 7,8,11,12` subset selection; per-experiment timeout 3600→7200s; merge preserves completed experiments; `git_sha` recorded | `campaign.yaml`, `campaign_runner.py`, `run_campaign.py`, `test_only_subset.py`; campaign_001 = 12/12 successful, 528 trajectory records for exp 7/8/11/12 |
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

**Entry point**: `package/evaluation/trajectory/score_trajectory.py` orchestrates all 5 layers per trajectory.
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
| `evaluate_product_reply.py` | Evaluates generated answers against recommended items (grounding check, format validation) |
| `evaluate_product_reply_with_jev.py` | LLM-as-judge (Jev/TypeSafe AI): faithfulness (claim extraction + support) + communication quality (1-5 scale: relevance, clarity, language, honesty_about_gaps) |

### 0.8.6. Campaign Runner (package/evaluation/campaign/)

| File | Purpose |
|------|---------|
| `campaign_runner.py` | Orchestrates multiple `run_agent_eval.py` experiments via subprocess; parameter grid expansion, comparison pairs, repetition |
| `checkpoint_manager.py` | Resume/crash recovery for long-running campaigns |
| `_schema.py` | Pydantic schemas for campaign config, experiment config, comparison pairs |

**Config**: `configs/evaluation/campaign.yaml` (parameter_grid, comparison_pairs, repetition_count, output_dir, per-experiment timeout — now 7200s)

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
| `configs/evaluation/` | `campaign.yaml` | Campaign orchestration (parameter grid, comparison pairs, repetition) |
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
| `--campaign-config` | `configs/evaluation/campaign.yaml` | Path to campaign YAML |
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
| `evaluation/campaign` | `configs/evaluation/campaign.yaml` | Campaign orchestration (parameter_grid, comparison_pairs, repetition) |
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
| `PYTHONPATH=. python scripts/evaluation/run_campaign.py --dry-run --campaign-config configs/evaluation/campaign.yaml` | ✅ | `--git-sha` auto-detected |
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

## 0.17. Glossary of Important Components and Terms

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
| **Oracle Request Kinds** | `constrained`, `cold_text` — use held-out target categories/prices. Upper bound, not real queries. |
| **CONFIG_OVERLAY_PATH** | Env var for per-experiment config overrides (used by campaign runner). |
| **Run Tag** | Identifier for artifact directories (from `run_tag.yaml`, default `multi_domain`). |
| **Provenance** | Artifact tracking: file_hash, mapping_hash, fit_provenance, git_sha, config hash. Path: `src/package/evaluation/provenance/` |
| **ScriptedLLM** | Test double in `package/evaluation/doubles/`: returns pre-scripted responses for testing. |
| **ScriptedJudge** | Test double in `package/evaluation/doubles/`: returns pre-scripted Jev-like judgments. |
| **Fake*Tool** | Test doubles in `package/evaluation/doubles/`: deterministic fake tools for benchmarks. |
| **Campaign** | Orchestrated experiment runner managing grid experiments with per-experiment artifacts. Path: `src/package/evaluation/campaign/` |---

## 0.18. Document Provenance

| Field | Value |
|-------|-------|
| **Document** | `src/Project repository reading 29.10.md` (updated in place) |
| **Update date** | 2026-11-14 |
| **Branch** | `tools-building` (evidence: `git rev-parse --abbrev-ref HEAD`) |
| **Commit** | `880bf5c` ("0749_1110") (evidence: `git log --oneline -1`) |
| **Working tree** | ~40 modified + ~70 untracked (evidence: `git status --short` → 112 lines; uncommitted evaluation work per §0.1.3) |
| **Key evidence sources** | Git commands (branch, log, status), pytest collection output, directory enumeration (Get-ChildItem), git log for phase history |
| **Unresolved evidence** | `resource/` data (missing), real LLM/Jev evaluation pending (planner baseline, −Rank arm), planner fixes not yet applied, final ablation numbers pending |---

**End of Repository Reading**
