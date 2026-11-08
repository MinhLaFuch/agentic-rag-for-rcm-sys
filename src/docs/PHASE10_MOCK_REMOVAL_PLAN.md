# Phase 10: Mock Removal Inventory Plan

## Objective
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

## STOP for Approval

This plan is ready for review. No deletions will be made until approval.
