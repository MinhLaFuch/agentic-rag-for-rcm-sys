# Phase 6: Complete List of Mock and Real Implementations

## 1. LLM Provider

### Real Implementation
**File:** `package/api/llm_provider.py`
- **Class:** `LLMProvider` (abstract base class)
- **Purpose:** Interface for all LLM backends
- **Methods:** `complete()`, `health_check()`
- **Implementations:** JevProvider (in `package/api/jev_provider.py`)

### Mock Implementation
**File:** `package/evaluation/component/benchmarks/mock_llm_provider.py`
- **Class:** `MockLLMProvider`
- **Purpose:** Returns deterministic canned responses for testing
- **Features:**
  - Takes `responses` dict mapping patterns to canned responses
  - Stores `last_messages` for inspection
  - Default fallback returns empty plan `{"steps": []}`
- **Used by:** planner_benchmark, get_mock_llm.py

### Mock Getter
**File:** `package/evaluation/component/benchmarks/get_mock_llm.py`
- **Function:** `get_mock_llm()`
- **Purpose:** Factory that returns MockLLMProvider with predefined responses

---

## 2. Tools

### Real Tools (in package/tools/)
- **SearchTool:** `package/tools/retrieval/search_tool.py` - FTS search over item metadata
- **SimilarTool:** `package/tools/ranking/similar_tool.py` - Item-to-item similarity (collaborative filtering)
- **RankTool:** `package/tools/ranking/rank_tool.py` - Rank candidates for a user
- **FilterTool:** `package/tools/sql/filter_tool.py` - Structured SQL filtering
- **LookupTool:** `package/tools/sql/lookup_tool.py` - SQL query tool
- **BaselineScorer:** `package/tools/scoring/baseline_scorer.py` - Baseline scoring for candidates
- **CandidateScorer:** `package/tools/scoring/candidate_scorer.py` - Candidate set scoring

### Simple Mock Tools (deterministic, return canned data)
**File:** `package/evaluation/component/benchmarks/mock_filter_tool.py`
- **Class:** `MockFilterTool`
- **Purpose:** Returns deterministic mock candidate list
- **Returns:** 5 mock items with incremental prices

**File:** `package/evaluation/component/benchmarks/mock_search_tool.py`
- **Class:** `MockSearchTool`
- **Purpose:** Returns deterministic mock search results
- **Returns:** 5 mock items with scores decreasing from 0.9

**File:** `package/evaluation/component/benchmarks/mock_rank_tool.py`
- **Class:** `MockRankTool`
- **Purpose:** Returns deterministic mock ranking
- **Returns:** Ranked candidates with scores decreasing from 0.9

**File:** `package/evaluation/component/benchmarks/mock_similar_tool.py`
- **Class:** `MockSimilarTool`
- **Purpose:** Returns deterministic mock similar items
- **Returns:** 5 mock similar items with similarities decreasing from 0.8

### Controlled Tools (failure injection - different semantics)
**File:** `package/evaluation/component/benchmarks/controlled_filter_tool.py`
- **Class:** `ControlledFilterTool`
- **Purpose:** Tool with controlled failure behavior for executor testing
- **Features:**
  - `should_fail`: Returns `{"ok": False, "data": {}, "error": "Simulated tool failure"}` (NOT a proper ToolResult)
  - `should_timeout`: Sleeps for 10 seconds
  - `should_return_empty`: Returns empty candidate list
- **Key difference:** Returns `ok=True` even when `should_fail=True` (failure nested in `data`)
- **Used by:** executor_benchmark, get_controlled_tools.py

**File:** `package/evaluation/component/benchmarks/controlled_similar_tool.py`
- **Class:** `ControlledSimilarTool`
- **Purpose:** SimilarTool with controlled failure behavior
- **Features:**
  - `should_fail`: Returns `{"ok": False, "data": {}, "error": "Simulated CF failure"}`
  - `should_return_empty`: Returns empty candidate list
- **Key difference:** Returns `ok=True` even when `should_fail=True` (failure nested in `data`)
- **Used by:** executor_benchmark, get_controlled_tools.py

### Mock Tool Getters
**File:** `package/evaluation/component/benchmarks/get_mock_tools.py`
- **Function:** `get_mock_tools()`
- **Purpose:** Returns simple mock tools (FilterTool, SearchTool, RankTool, SimilarTool)

**File:** `package/evaluation/component/benchmarks/get_controlled_tools.py`
- **Function:** `get_controlled_tools()`
- **Purpose:** Returns controlled tools (ControlledFilterTool, ControlledSimilarTool)

---

## 3. Backend

### Real Implementation
**File:** `package/demo/backend/live_backend.py`
- **Class:** `LiveBackend`
- **Purpose:** Real backend using PlanExecutor and Type1Agent with real data
- **Features:**
  - Loads real data (mappings, splits, corpus, recommender)
  - Uses real LLM (via build_llm_provider)
  - Uses real PlanExecutor or Type1Agent
  - Handles memory snapshots
  - Processes real requests

### Mock Implementation
**File:** `package/demo/backend/mock_backend.py`
- **Class:** `MockBackend`
- **Purpose:** Returns predetermined responses for demo without needing data/LLM/network
- **Features:**
  - 4 mock profiles (blank, cold, sparse, warm)
  - 4 mock statuses (ok, ask_user, no_result, tool_error) that cycle
  - Mock items (3 sample items)
  - Mock memory view based on user_id
  - Mock traces with pre-built steps
- **Used by:** demo scripts for testing

---

## 4. Other Mocks in Tests (not in package/)

### Test-only doubles in tests/agents/fakes/
**File:** `tests/agents/fakes/fake_tools.py`
- **FakeModel:** Fake recommender model for testing
- **FakeScorer:** Fake scorer for testing
- **FakeTools:** Collection of fake tools

**File:** `tests/agents/fakes/scripted_llm.py`
- **ScriptedLLM:** LLM that returns pre-scripted responses

**File:** `tests/agents/test_memory_tool.py`
- Has inline ScriptedLLM definition (duplicate of above)

**File:** `tests/demo/test_live_backend.py`
- Has inline ScriptedLLM definition (duplicate of above)

---

## Summary by Category

### A. Has both real and mock implementations
1. **LLM Provider:**
   - Real: `LLMProvider` (abstract), `JevProvider` (implementation)
   - Mock: `MockLLMProvider`
   - Mock getter: `get_mock_llm()`

2. **Backend:**
   - Real: `LiveBackend`
   - Mock: `MockBackend`

### B. Has mock tools but real tools are different implementations
1. **Tools:**
   - Real: SearchTool, SimilarTool, RankTool, FilterTool (use real data/corpus)
   - Simple mocks: MockFilterTool, MockSearchTool, MockRankTool, MockSimilarTool (return canned data)
   - Controlled mocks: ControlledFilterTool, ControlledSimilarTool (failure injection)
   - Mock getters: `get_mock_tools()`, `get_controlled_tools()`

### C. Test-only doubles (no real counterpart in package/)
- FakeModel, FakeScorer, FakeTools, ScriptedLLM (in tests/agents/fakes/)

---

## Decision Points

### For each pair/cluster, you need to decide:

**1. LLM Provider (JevProvider vs MockLLMProvider):**
- Option A: Merge into `llm_provider.py` with `mock: bool` parameter
- Option B: Keep separate, add factory pattern
- Option C: Keep as-is

**2. Backend (LiveBackend vs MockBackend):**
- Option A: Merge into backend factory with `mock: bool` parameter
- Option B: Keep separate, add factory pattern
- Option C: Keep as-is

**3. Simple Mock Tools (MockFilterTool, MockSearchTool, MockRankTool, MockSimilarTool):**
- Option A: Delete (controlled tools cover the use cases)
- Option B: Merge into real tools with `mock: bool` parameter
- Option C: Keep as-is

**4. Controlled Tools (ControlledFilterTool, ControlledSimilarTool):**
- Option A: Merge into real tools with `controlled: bool` parameter
- Option B: Keep as-is (different semantics, used for specific executor testing)
- Option C: Move to a different location

**5. Test-only doubles (FakeModel, FakeScorer, FakeTools, ScriptedLLM):**
- Option A: Consolidate into single `tests/fakes/` directory
- Option B: Keep as-is (they're test-only, intentionally separate from package)
- Option C: Move to `package/testing/` (violates architecture rule)

---

## Current Usage

**Where are mocks used?**
- `planner_benchmark.py`: Uses real LLM + mock tools
- `executor_benchmark.py`: Uses mock LLM + controlled tools
- `run_demo.py`: Has `--mock` flag (uses MockBackend when enabled)
- Demo scripts: Can use MockBackend for testing
- Component benchmarks: Use mock tools for controlled testing

**Where are real implementations used?**
- Production: JevProvider, LiveBackend, real tools
- Type1Agent: Uses real tools
- PlanExecutor: Uses real tools
