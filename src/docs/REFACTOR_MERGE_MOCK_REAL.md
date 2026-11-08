# Phase 6: Merge Mock and Real Implementations

## Principle
Code in `package/` does not know mock vs real, only receives injected `llm`, `tools`, `judge`. Only entry point (script) chooses real vs fake via `--mock`.

## Decisions

| Category | Decision |
|---|---|
| Delete simple Mock*Tool? | YES, replace with Fake*Tool in same commit (internal repo, no backward compat needed) |
| Merge controlled with controlled flag? | NO, replace with Fake*Tool(fixed_error=..., delay_seconds=...) |
| --mock for which scripts? | Only scripts that generate eval data or need LLM/data: run_agent_eval, run_campaign, link_e2e_cli, CLI component benchmark, multi-turn, run_demo (already has), demo_full_agent (check). Real smoke, run_tools, data pipeline - no flag |
| Real smoke tests (jev_smoke_test, smoke_real_llm) | Keep, they're real smoke tests |
| test_phase1_smoke | Keep, it fakes at HTTP boundary so still tests real provider code |
| 5 integration tests | Keep in place, add pytest marker `integration` to select/exclude with -m. Don't move directory |
| link_e2e_cli | Real mode reads real result files. Hard-coded data only for --mock |
| Double placement | Single location. Priority: package/evaluation/doubles/ (tests can import from package, benchmarks can use). If architecture rule forbids, use tests/fakes/, only scripts/tests import |

## Implementation Phases (in order)

### Phase A: Verification (no code changes)
- Quote original text from test_dependency_direction and test_package_layout rules to decide double placement
- Verify paths against current tree (fix: package/tools/sql/ not sql_query/, build_judgment_provider is separate file)
- List which scripts call judge, LLM, or data
- Read demo_full_agent.py to check if it uses mock or real
- Check which benchmarks use which doubles

### Phase B: Fix bug
- Change Controlled* to raise ToolInputError instead of returning ok=True with error in data
- Add regression test calling through __call__ and assert ok is False
- This test must survive Phase C

### Phase C: Consolidate doubles
- Fake*Tool ×6 with schema copied from real class, plus delay_seconds
- Single ScriptedLLM (absorbs MockLLMProvider, default script becomes default_planner_script())
- Single ScriptedJudge for --mock in judge portion
- Move create_test_* to fixtures/
- Expand test_fake_contracts to cover all (tool, LLM, judge)

### Phase D: Add --mock flag
- build_runtime(mock) returns llm/tools/judge/data
- Add add_mock_argument(parser)
- Default is real. Missing conditions (LLM_BASE_URL, data) fail fast, never auto-fallback to mock
- Banner shows "MOCK MODE", write to directory/run tag with -mock suffix, provenance has "mode": "mock"

### Phase E: Remove pseudo-real results
- Replace MockAgentRunner with runner using real Session (mock mode only replaces part with fake)
- planner_benchmark uses real schema, or records "tools": "fake" in provenance if real data not available

### Phase F: Cleanup
- Delete mock_*_tool ×4, controlled_* ×2, mock_llm_provider, get_mock_llm, get_mock_tools, get_controlled_tools
- Delete 2 inline ScriptedLLM copies in tests
- Rename MockBackend to OfflineDemoBackend with factory get_backend(mock)
- Update imports and README

### Phase G: Pytest markers (low risk, do last)
- Add integration marker
- Document in tests/README.md: unit / integration / real smoke categories

## Pending Decision
Only double placement depends on architecture rule that Phase A will extract. Everything else is pre-decided.
