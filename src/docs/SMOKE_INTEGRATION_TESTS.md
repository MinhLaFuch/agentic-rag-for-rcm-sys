# Smoke Scripts and Integration Tests - Complete List

## Smoke Scripts (scripts/)

### 1. scripts/evaluation/jev_smoke_test.py
**Purpose:** Smoke test for real Jev provider integration
**Requires:** TYPESAFE_API_KEY environment variable
**Tests:**
- JevProvider connectivity
- Simple Noul evaluation
- Full product reply evaluation with Jev
**Uses:** Real JevProvider, real LLM
**Status:** Production smoke test (needs real API key)

### 2. scripts/llm_agent/smoke_real_llm.py
**Purpose:** Smoke test for PlanExecutor with real LLM
**Tests:**
- PlanExecutor with 5 tools on synthetic fixture
- Uses real LLM from configs/agent/llm.yaml
- 3 test requests with synthetic data
**Uses:** Real LLM (via build_llm_provider), synthetic corpus/recommender
**Status:** Production smoke test (needs real LLM access)

### 3. scripts/demo/run_demo.py
**Purpose:** Demo script with --mock flag
**Features:**
- Has --mock flag to use MockBackend instead of LiveBackend
- When --mock, uses MockBackend (no data/LLM needed)
- When not --mock, uses LiveBackend (needs real data/LLM)
**Uses:** Can use MockBackend or LiveBackend
**Status:** Demo script (has mock switch)

---

## Smoke Tests (tests/)

### 1. tests/agents/test_phase1_smoke.py
**Purpose:** End-to-end smoke test for config -> factory -> provider chain
**Tests:**
- test_end_to_end_agent_config_to_llm_call: Mocks HTTP request, tests config loading and provider building
- test_end_to_end_data_config: Tests data config loading
**Uses:** Fake HTTP response (no real network call), config loading
**Status:** Unit test with mocked HTTP (no external dependencies)

---

## Integration Tests (tests/)

### 1. tests/agents/test_plan_executor.py
**Purpose:** Tests PlanExecutor behavior
**Uses:** Mock LLM (ScriptedLLM defined inline), synthetic tools
**Status:** Integration test with mocked LLM

### 2. tests/tools/integration/test_tools_integration.py
**Purpose:** Tests tool integration
**Uses:** Real tools with synthetic corpus
**Status:** Integration test (no mocks, real tools with test data)

### 3. tests/evaluation/ablation/test_integration.py
**Purpose:** Ablation study integration test
**Uses:** Real evaluation components
**Status:** Integration test

### 4. tests/evaluation/agent/test_eval_integration.py
**Purpose:** Agent evaluation integration test
**Uses:** Real agent evaluation components
**Status:** Integration test

### 5. tests/evaluation/component/benchmarks/test_grounding_benchmark.py
**Purpose:** Grounding benchmark
**Uses:** Real tools and evaluation components
**Status:** Integration test (benchmark)

---

## Other Scripts (may use mocks)

### scripts/evaluation/link_e2e_cli.py
**Purpose:** E2E CLI for link evaluation
**Uses:** Hard-coded results (mock-like behavior)
**Status:** CLI script with mock results

### scripts/tools/run_tools.py
**Purpose:** Run tools individually
**Uses:** Real tools
**Status:** Tool runner script

### scripts/demo/demo_full_agent.py
**Purpose:** Demo script
**Uses:** May use mock or real backend
**Status:** Demo script

---

## Duplicate ScriptedLLM Definitions

**Location 1:** tests/agents/fakes/scripted_llm.py
**Location 2:** tests/agents/test_memory_tool.py (inline definition)
**Location 3:** tests/demo/test_live_backend.py (inline definition)

These are duplicates of the same ScriptedLLM class.

---

## Summary by Category

### A. Production Smoke Tests (need real API/LLM)
1. scripts/evaluation/jev_smoke_test.py (needs TYPESAFE_API_KEY)
2. scripts/llm_agent/smoke_real_llm.py (needs real LLM access)

### B. Unit Tests with Mocks
1. tests/agents/test_phase1_smoke.py (mocks HTTP, no real network)

### C. Integration Tests (use real components with test data)
1. tests/agents/test_plan_executor.py (uses ScriptedLLM)
2. tests/tools/integration/test_tools_integration.py (real tools, synthetic data)
3. tests/evaluation/ablation/test_integration.py
4. tests/evaluation/agent/test_eval_integration.py
5. tests/evaluation/component/benchmarks/test_grounding_benchmark.py

### D. Demo Scripts with Mock Option
1. scripts/demo/run_demo.py (has --mock flag)
2. scripts/demo/demo_full_agent.py

### E. Scripts with Mock Results
1. scripts/evaluation/link_e2e_cli.py (hard-coded results)

### F. Duplicate Code
1. ScriptedLLM defined in 3 places (tests/agents/fakes/scripted_llm.py, tests/agents/test_memory_tool.py, tests/demo/test_live_backend.py)

---

## Cleanup Options

For each category, you need to decide:

**A. Production Smoke Tests (scripts/evaluation/jev_smoke_test.py, scripts/llm_agent/smoke_real_llm.py):**
- Option 1: Keep as-is (they serve a purpose for validating real integrations)
- Option 2: Add --mock flag to also support mock mode
- Option 3: Delete (if you don't need real smoke tests)

**B. Unit Test with Mocks (tests/agents/test_phase1_smoke.py):**
- Option 1: Keep as-is (it's a good unit test)
- Option 2: Move to a different location
- Option 3: Delete

**C. Integration Tests (5 files):**
- Option 1: Keep as-is (they validate real integration)
- Option 2: Consolidate into single tests/integration/ directory
- Option 3: Add mock modes to all of them
- Option 4: Delete some/all

**D. Demo Scripts with Mock Option (scripts/demo/run_demo.py, scripts/demo/demo_full_agent.py):**
- Option 1: Keep as-is (already has --mock)
- Option 2: Standardize mock flag across all demo scripts
- Option 3: Remove mock mode, always use real

**E. Scripts with Mock Results (scripts/evaluation/link_e2e_cli.py):**
- Option 1: Keep as-is (for quick testing without real data)
- Option 2: Make it use real data instead of hard-coded results
- Option 3: Delete

**F. Duplicate ScriptedLLM (3 locations):**
- Option 1: Consolidate to tests/agents/fakes/scripted_llm.py, import from other files
- Option 2: Move to package/testing/ (violates architecture rule)
- Option 3: Keep as-is (duplicates are acceptable for test isolation)
