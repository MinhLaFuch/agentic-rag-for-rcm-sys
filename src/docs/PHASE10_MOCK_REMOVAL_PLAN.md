# Phase 10: Mock Removal Inventory Plan

## Baseline B

**Test Results (2026-11-08):**
- **1327 passed**, 8 skipped, 2 xfailed, 19 warnings
- **0 failed**

**Changes from Phase 0 baseline (~1306 passed, 9 failed, 4 skipped, 2 xfailed):**
- +21 tests collected (new tests added during refactor)
- -9 failures fixed (import errors resolved)
- +4 skips (timeout tests skipped during Phase 4)
- Same 2 xfailed

**Warnings:** 19 total
- 5 PytestUnknownMarkWarning for `integration` marker (now registered in pyproject.toml)
- 13 SparseEfficiencyWarning (scipy sparse matrix operations)
- 1 other warning

**Test files touched during baseline establishment:**
- `tests/demo/test_demo_backend.py` - Fixed MockBackend → OfflineDemoBackend import
- `tests/demo/test_gradio_ui.py` - Fixed MockBackend → OfflineDemoBackend import
- `tests/evaluation/component/benchmarks/test_controlled_tools.py` - Updated to check ToolResult.ok is False
- `tests/evaluation/test_jev_reliability.py` - Fixed patch path for moved module
- `tests/tools/conftest.py` - Fixed ItemCorpus import from package.corpus
- `tests/tools/integration/test_tools_integration.py` - Fixed ItemCorpus import
- `tests/tools/retrieval/test_contract_retrieval.py` - Fixed ItemCorpus/SearchTool imports
- `tests/tools/retrieval/test_semantic_search_regressions.py` - Fixed ItemCorpus/SearchTool imports
- `package/data/pipeline/build_artifacts.py` - Fixed select_fit_target import
- `package/demo/backend/live_backend.py` - Fixed select_fit_target and BaselineScorer imports
- `scripts/evaluation/run_agent_eval.py` - Fixed save_experiment import

**Package layout test exceptions added (temporary):**
- `tests/config/test_package_layout.py` - Added SKIPPED_STEMS for mock/fake files, PRIVATE_IMPORT_EXCEPTIONS for cross-folder private imports

**Objective**
Remove everything that runs on fakes from `package/` and `scripts/`. Real only - no mock/fake/offline mode. Tests keep using fakes (out of scope for cleanup).

## Inventory

### 1. package/evaluation/doubles/*
**Files:**
- `__init__.py`
- `fake_judge.py` (ScriptedJudge)
- `fake_llm.py` (ScriptedLLM)
- `fake_tools.py` (FakeFilterTool, FakeSearchTool, FakeRankTool, FakeSimilarTool, FakeLookupTool)

**Importers in package/:**
- `package/evaluation/component/benchmarks/planner_benchmark.py` - uses Fake*Tool
- `package/evaluation/component/benchmarks/executor_benchmark.py` - uses ScriptedLLM
- `package/evaluation/component/run_benchmark_cli.py` - imports mock helper

**Importers in scripts/:**
- `scripts/_runtime_factory.py` - imports all doubles

**Importers in tests/:**
- NONE found

**Decision:** DELETE after updating benchmarks to use real components or remove fake-dependent scenarios

---

### 2. package/evaluation/component/benchmarks/controlled_*.py
**Files:**
- `controlled_filter_tool.py` (ControlledFilterTool)
- `controlled_similar_tool.py` (ControlledSimilarTool)
- `get_controlled_tools.py` (get_controlled_tools)

**Importers in package/:**
- `package/evaluation/component/benchmarks/executor_benchmark.py` - uses Controlled*Tool
- `package/evaluation/component/benchmarks/__init__.py` - exports them

**Importers in tests/:**
- `tests/evaluation/component/benchmarks/test_controlled_tools.py` - regression test

**Decision:** DELETE executor_benchmark scenarios that rely on injected failures. MOVE-TO-tests: test_controlled_tools.py needs the fakes relocated to tests/.

---

### 3. package/demo/backend/offline_backend.py
**File:**
- `offline_backend.py` (OfflineDemoBackend)

**Importers in package/:**
- `package/demo/backend/__init__.py` - exports it
- `package/demo/__init__.py` - exports it

**Importers in scripts/:**
- `scripts/demo/run_demo.py` - imports OfflineDemoBackend, uses get_backend(mock=True)

**Importers in tests/:**
- `tests/demo/test_gradio_ui.py` - imports MockBackend (old name)

**Decision:** DELETE OfflineDemoBackend and get_backend(mock). MOVE-TO-tests: test_gradio_ui.py needs fake backend relocated to tests/.

---

### 4. MockAgentRunner
**File:**
- `package/evaluation/multi_turn/_run.py` (MockAgentRunner class)

**Importers in package/:**
- `package/evaluation/multi_turn/_run.py` - defined and used internally

**Importers in scripts/:**
- NONE found (multi-turn CLI uses it internally)

**Importers in tests/:**
- NONE found

**Decision:** DELETE MockAgentRunner. Multi-turn CLI exits non-zero with "real runner not implemented yet" until Session-based runner exists.

---

### 5. --mock flag and related infrastructure
**Files:**
- `scripts/_mock_helper.py` (add_mock_argument, check_mock_conditions)
- `scripts/_runtime_factory.py` (build_runtime)

**Importers in scripts/:**
- `scripts/evaluation/run_agent_eval.py` - uses add_mock_argument, check_mock_conditions
- `scripts/evaluation/run_campaign.py` - uses add_mock_argument, check_mock_conditions
- `scripts/evaluation/link_e2e_cli.py` - uses add_mock_argument
- `package/evaluation/component/run_benchmark_cli.py` - uses add_mock_argument, check_mock_conditions
- `scripts/demo/run_demo.py` - uses --mock flag

**Importers in tests/:**
- NONE found

**Decision:** DELETE --mock flag, mode field, -mock suffix, build_runtime's mock branch, add_mock_argument, check_mock_conditions. Real mode fails fast with clear message when prerequisites missing.

---

### 6. package/evaluation/component/benchmarks/fixtures/*
**Files:**
- `fixtures/create_test_interactions.py`
- `fixtures/create_test_corpus.py`
- `fixtures/create_test_meta.py`
- `fixtures/create_test_mappings.py`

**Importers in package/:**
- `package/evaluation/component/benchmarks/build_cases.py` - uses create_test_*
- `package/evaluation/component/benchmarks/memory_correctness_setup.py` - uses create_test_*
- `package/evaluation/component/benchmarks/__init__.py` - exports them

**Importers in tests/:**
- `tests/evaluation/component/test_memory_correctness.py` - imports from memory_correctness_setup

**Decision:** KEEP what real-LLM benchmark or smoke script uses (planner_benchmark, smoke_real_llm). MOVE-TO-tests only what tests alone import. DELETE what nothing uses.

---

### 7. link_e2e_cli.py hard-coded results
**File:**
- `scripts/evaluation/link_e2e_cli.py`

**Current state:**
- Has hard-coded mock results in --mock mode
- Real mode loads from files (already implemented)

**Decision:** DELETE hard-coded results. Keep only real file loading.

---

### 8. executor_benchmark failure injection scenarios
**File:**
- `package/evaluation/component/benchmarks/executor_benchmark.py`

**Current state:**
- Uses Controlled*Tool with should_fail, should_timeout, should_return_empty
- These scenarios rely on injected failures

**Decision:** REMOVE failure-injection scenarios or mark them clearly as not runnable without fakes. Report which scenarios removed.

---

### 9. docs/README mentions of mock mode
**Files to check:**
- scripts/README.md
- package/evaluation/component/README.md
- tests/README.md
- docs/*.md

**Decision:** Update to remove mock mode mentions after deletion.

---

## Execution Steps (10.1)

1. **Minimal test fixes first:** Relocate fakes that tests import from package/ into tests/ (copy as-is, no cleanup). Repoint test imports. Run suite.
   - test_controlled_tools.py → needs Controlled*Tool relocated to tests/
   - test_gradio_ui.py → needs MockBackend/OfflineDemoBackend relocated to tests/

2. **Remove mock mode from scripts/CLIs:** Delete --mock, mode, -mock suffix, build_runtime's mock branch, add_mock_argument. Real mode fails fast with clear message.
   - run_agent_eval.py
   - run_campaign.py
   - link_e2e_cli.py
   - package/evaluation/component/run_benchmark_cli.py
   - scripts/demo/run_demo.py

3. **Demo:** Delete OfflineDemoBackend and get_backend(mock). Fix demo test minimally.

4. **Multi-turn:** Delete MockAgentRunner; CLI exits non-zero with "real runner not implemented yet".

5. **Benchmarks:** planner_benchmark uses real LLM + real tools over fixtures. executor_benchmark: remove injected-failure scenarios or mark as not runnable.

6. **Delete package/evaluation/doubles/** and unused fixtures. Update docs/README.

7. **Grep proof:** No mock/Mock/Controlled/--mock/Scripted/Fake left in package/ or scripts/.

## Test Files Requiring Minimal Fixes

| Test File | Current Import | Needs Relocation |
|-----------|---------------|------------------|
| tests/evaluation/component/benchmarks/test_controlled_tools.py | package.evaluation.component.benchmarks.controlled_* | Controlled*Tool → tests/ |
| tests/demo/test_gradio_ui.py | package.demo.MockBackend (old name) | OfflineDemoBackend → tests/ |

## Deferred Work (docs/TODO_TESTS_CLEANUP.md)

- One home and one copy for fakes in tests/
- Tests mirror package/ structure
- tests/architecture/ for layout tests
- Fake contract tests
- Executor benchmark failure-injection scenarios as pytest tests

---

## Verification (answers to pre-deletion questions)

### 1. Test impact — every test importing package/ mock code

Grep of `tests/` for `package.evaluation.doubles`, `controlled_*`, `OfflineDemoBackend`, `MockBackend`, `MockAgentRunner`, `_mock_helper`, `_runtime_factory`, `get_backend`, `fixtures`:

| Test file | Imports from package/ | Minimal fix |
|---|---|---|
| `tests/demo/test_demo_backend.py` | `OfflineDemoBackend` from `package.demo` | Relocate `offline_backend.py` → `tests/demo/fakes/offline_backend.py`, repoint import |
| `tests/demo/test_gradio_ui.py` | `OfflineDemoBackend` from `package.demo` | Same relocated fake |
| `tests/evaluation/component/benchmarks/test_controlled_tools.py` | `ControlledFilterTool`, `ControlledSimilarTool` | Relocate both → `tests/evaluation/component/benchmarks/fakes/` |
| `tests/evaluation/component/test_memory_correctness.py` | `memory_correctness_setup` (re-exports `create_test_*`) | Keep — `memory_correctness_setup` stays in package/ (real benchmark uses it); only its `.fixtures` imports stay |

No test imports `package.evaluation.doubles`, `MockAgentRunner`, `_mock_helper`, `_runtime_factory`, `get_backend`, or `fixtures/` directly. No test asserts `--mock` CLI behavior.

### 2. Controlled*Tool
Move `controlled_filter_tool.py` + `controlled_similar_tool.py` to `tests/evaluation/component/benchmarks/fakes/` as-is (copy, delete from package/). `get_controlled_tools.py` is deleted (only `executor_benchmark` uses it, which loses its failure scenarios). `test_controlled_tools.py` keeps asserting `result.ok is False` and `result.error is not None` — unchanged strength.

### 3. executor_benchmark injected-failure scenarios
`executor_benchmark.py` builds `ControlledFilterTool`/`ControlledSimilarTool` with `should_fail`, `should_timeout`, `should_return_empty` read from per-tool config (`tool_config`). After Controlled* are gone, these scenarios cannot run. Action: remove the Controlled* import and the failure-injection config path; the benchmark then runs only real-tool scenarios (FilterTool/SimilarTool with real corpus) or reports "no runnable scenarios" when only fake-dependent cases exist. Nothing moves to tests/ in this phase.

### 4. Multi-turn CLI
`package/evaluation/multi_turn/_run.py` line 72 constructs `MockAgentRunner(config)`; the class is defined at line 136. After deletion the module raises `NotImplementedError("real runner not implemented yet")` at the runner construction point; verified by running the multi-turn entry after the edit.

### 5. Other fake-substitution paths
Grep of `package/` + `scripts/` for `mock|Mock|fake|Fake|controlled|Controlled|offline|Offline|Scripted`: hits are exactly the inventoried items — `doubles/`, `controlled_*`, `offline_backend.py`, `MockAgentRunner` in `_run.py`, `--mock` in `run_agent_eval.py`, `run_campaign.py`, `link_e2e_cli.py`, `run_benchmark_cli.py`, `run_demo.py`, `demo_full_agent.py` (imports only), plus `build_runtime`/`add_mock_argument`/`check_mock_conditions` in `scripts/_mock_helper.py` + `scripts/_runtime_factory.py`. `openai_compatible_provider.py`, `build_requests.py`, `analyze_ranking_bottlenecks.py`, `candidate_recall.py`, `recommenders/*` hits are incidental words (e.g. "mock" in comments) — no fake substitution. `planner_benchmark.py` uses `Fake*Tool` (covered). No other paths found.

### 6. fixtures/ KEEP list
`package/evaluation/component/benchmarks/fixtures/` is imported by:
- `build_cases.py` → `create_test_interactions`, `create_test_mappings`, `create_test_meta` (memory correctness dataset builder — real benchmark path)
- `memory_correctness_setup.py` → all four `create_test_*` (used by `run_benchmark_cli.py` memory evaluator and `test_memory_correctness.py`)
- `benchmarks/__init__.py` → re-exports all four

KEEP all four: they are synthetic data builders for the real MemoryCorrectness benchmark, not mock behavior. `planner_benchmark.py` and `smoke_real_llm.py` do NOT import them (verified — no hits). Nothing in fixtures/ is deleted.

---

## STOP for Approval

This plan is ready for review. No deletions will be made until approval.
