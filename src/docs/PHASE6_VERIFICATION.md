# Phase 6A: Verification Findings

## Architecture Rules

From test_dependency_direction.py:
- tools → must not import agents
- agents → must not import inference / demo / evaluation
- inference → may import agents (not demo / evaluation)
- evaluation → may import agents / inference (not demo)
- demo → may import agents / inference (not evaluation)
- Only package/ is checked; scripts/ and tests/ are exempt

From test_package_layout.py:
- Tests/ may import privates (white-box tests)
- Scripts/ are checked for layout violations
- Cross-folder imports of _ modules are forbidden

## Double Placement Decision

**Rule:** Tests can import from package, but package must not import from tests. Scripts can import from package and tests (entry points exempt).

**Decision:** Use `package/evaluation/doubles/` for test doubles
- Tests can import from package/evaluation/doubles/ (allowed)
- Benchmarks (in package/evaluation/component/benchmarks/) can import from package/evaluation/doubles/ (allowed, same package)
- Scripts can import from package/evaluation/doubles/ (allowed, entry points exempt)
- Package modules will NOT import from tests (satisfies dependency direction rule)

**Alternative:** If forbidden, use `tests/fakes/` and only scripts/tests import it. But this prevents benchmarks from using the doubles, which would require restructuring.

## Path Verification

**Current tree (after Phase 4):**
- package/tools/sql/ (was sql_query/, renamed in Phase 4)
- package/api/llm_provider.py (separate from jev_provider.py)
- package/api/jev_provider.py (separate file)
- package/api/build_judgment_provider.py (separate file)

**Scripts calling judge/LLM/data:**
- scripts/demo/demo_full_agent.py - uses build_llm_provider, real LLM
- scripts/demo/run_demo.py - has --mock flag
- scripts/evaluation/evaluate_with_jev.py - uses Jev
- scripts/evaluation/jev_smoke_test.py - uses Jev (real smoke test)
- scripts/evaluation/run_agent_eval.py - needs LLM
- scripts/llm_agent/smoke_real_llm.py - uses real LLM
- scripts/tools/check_llm_provider.py - checks LLM provider

**demo_full_agent.py:**
- Uses real LLM (build_llm_provider)
- Has commented code for real data loading
- Currently raises SystemExit if run directly (intended as module import only)

**Benchmarks using doubles:**
- planner_benchmark.py - uses mock tools (MockFilterTool, MockSearchTool, MockRankTool, MockSimilarTool)
- executor_benchmark.py - uses controlled tools (ControlledFilterTool, ControlledSimilarTool)
- get_mock_tools.py - returns simple mock tools
- get_controlled_tools.py - returns controlled tools
- create_test_*.py - creates test data

## Phase A Conclusion

**Double placement:** `package/evaluation/doubles/` (tests and benchmarks can import, no rule violation)

**Scripts needing --mock:**
- run_agent_eval
- run_campaign
- link_e2e_cli
- CLI component benchmark
- multi-turn scripts
- run_demo (already has)
- demo_full_agent (needs check/implementation)

**Scripts without --mock:**
- jev_smoke_test (real smoke test, keep real)
- smoke_real_llm (real smoke test, keep real)
- run_tools (tool runner, no LLM/data needed)
- data pipeline scripts (no LLM needed)

**Ready for Phase B: Fix bug in Controlled* tools**
