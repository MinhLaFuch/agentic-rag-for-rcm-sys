# Repository Reading Update Log

**Update Date**: 2026-11-12
**Branch**: tools-building
**Commit**: 880bf5c (" 0749_1110\)


---

## 1. Section Changes: Old vs New vs Evidence

| Section | Old Value | New Value | Evidence |
|---------|-----------|-----------|----------|
| 0.1 Front Matter | branch: refactor-phase-0, commit: 7c755a0, updated: 2026-11-08 | branch: tools-building, commit: 880bf5c, updated: 2026-11-12 | git rev-parse --abbrev-ref HEAD, git log --oneline -1 |
| 0.1 Test Baseline | 368 passed, 4 skipped, 6 warnings | 1696 tests collected | python -m pytest --collect-only -q |
| 0.1.1 Package Structure | tools/{corpus,recommenders,score,sql_query,evaluation} | {corpus,recommenders,tools/{scoring,sql,ranking,retrieval,base},utils} + evaluation expanded | Get-ChildItem src/package/ |
| 0.1.1 Tools | 6 tools in package/tools/ | 6 tools in package/tools/{retrieval,ranking,scoring,sql,base} + package/utils/ | Get-ChildItem src/package/tools/, src/package/utils/ |
| 0.1.1 Component Benchmarks | 5 components, mostly TODO | 5 components maintained; campaign integration added | src/package/evaluation/component/benchmarks/, src/package/evaluation/campaign/ |
| 0.1.2 Phase Table | Phases 0-8 Complete | Phases 0-10.1 Complete (added Phase 9, 10, 10.1) | Git log: 12b287e, eb0a449, 18d33a2, 708149b, 987880f, 880bf5c |
| 0.2 Directory Tree | campaign/ listed twice under evaluation/; tools/utils/ existed | campaign/ appears once at package/evaluation/campaign/; tools/utils/ does NOT exist; utils/ at package/utils/ | Get-ChildItem src/package/evaluation/, src/package/tools/, src/package/utils/ |
| 0.3 PlanExecutor | package/agents/plan_executor.py | package/agents/planner/plan_executor.py | Get-ChildItem src/package/agents/planner/ |
| 0.3 Type1Agent | package/agents/type1_agent.py | package/agents/type1/type1_agent.py | Get-ChildItem src/package/agents/type1/ |
| 0.5 Six Tools Table | Various incorrect paths | Corrected paths for all 6 tools | src/package/agents/toolkit/agent_tools.py, directory structure |
| 0.5 Planner? Column | Based on old structure | Derived from agent_tools.py for_planner()/for_planner_memory() | agent_tools.py lines 22-26 |
| 0.5 Embeddings | NOT IMPLEMENTED in package/tools/embeddings/ | Optional primitives in package/embeddings/ NOT wired into agent tool chain | package/embeddings/__init__.py lines 1-10 |
| 0.6 Inference Functions | Various paths | compose_llm: package/inference/compose/compose_llm.py; compose_template: package/inference/compose/compose_template.py; check_grounding: package/inference/grounding/check_grounding.py | Source files exist at those paths |
| 0.6 Configs/agent/ | Not listed | 11 YAML files enumerated | Get-ChildItem src/configs/agent/ |
| 0.6 Agent Types Table | Old agent list | Updated vs agent_eval.yaml: baseline, type1, planner, planner_memory | configs/agent/agent_eval.yaml lines 5-10 |
| 0.4 Pipeline | Old 4-stage + 5 components | Updated with 6 components (added multi_turn), unified runner, campaign orchestration | component_benchmarks.yaml, _run_all.py, campaign_runner.py |
| 0.8 Evaluation Framework | Old layer structure | 5-layer + 6 component benchmarks + test doubles in tests/agents/fakes/ | Source code inspection |
| 0.9 Entry Points | Old script list | 14 primary scripts with verified CLI flags | Source code inspection of each script |
| 0.9 CLI Flags | Some flags unverified | 28 flags verified across scripts | argparse definitions in each script |
| 0.10 Config Inventory | Not detailed | 33 YAML configs across 5 categories | Get-ChildItem on each configs/ subdir |
| 0.11 Artifacts | Old paths | Updated paths including campaign_001_summary.md | data_paths.yaml, actual experiment outputs |
| 0.11.7 Config Reference Table | Misaligned columns | Fixed alignment (31 entries) | Manual correction based on actual configs |
| 0.12 Test Counts | 368 passed | 1696 collected | pytest --collect-only output |
| 0.13.1 tool_selection_accuracy | low | 0.4904 | unified_report_20261110_210732.md:66 |
| 0.13.1 reflection_rescued | 0.0 | NOT measured in executor benchmark (scope is _execute only) | executor_benchmark.py:8-11 |
| 0.13.1 grounding_rate | 0.0 | 0.6714 (hallucination_rate: 0.3286) | unified_report_20261110_210732.md:120 |
| 0.13.2 Multi-turn | Not real-LLM evaluated | Runs on synthetic fixture corpus; MockAgentRunner still in place | unified_report_20261110_210732.md:152 |
| 0.13.3 Campaign Runner | Unverified | Verified with artifacts: campaign_001 completed 8/12 runs | campaign_001_summary.md, src/experiments/agent_eval/campaigns/campaign_001/ |
| 0.13.4 resource/ data | Missing | Exists at src/resource/ with all pipeline artifacts | Directory listing |
| 0.14 Limitations | Old status | Updated with actual benchmark values and campaign status | unified_report, campaign_001_summary.md |
| 0.16 Future Work | All pending | 3 items marked DONE: Component benchmarks, Multi-turn framework, Campaign runner | unified_report, campaign artifacts |
| 0.16 Future Work | No chua co artifact xac nhan | Added for all unverified claims | -- |
| 0.17 Glossary | Old paths | Updated paths for PlanExecutor, Type1Agent, test doubles location | Source code inspection |
| 0.18 Provenance | Old branch/commit | Updated to tools-building / 880bf5c | Git commands |

---

## 2. Unresolved Contradictions

| Issue | Description | Suggested Resolution |
|-------|-------------|----------------------|
| Real LLM Evaluation | Planner benchmark requires LLM_BASE_URL/LLM_API_KEY not set; no real-provider agent evaluation possible | Set credentials or document as environmental blocker |
| Real Jev Evaluation | Grounding benchmark uses ScriptedJudge; real Jev requires TYPESAFE_API_KEY not set | Set credentials or document as environmental blocker |
| Retrieval Recall | BM25 recall experiments exist but not run on real catalog (resource/ exists but experiments not executed) | Run candidate_recall experiments to quantify upstream bottleneck |
| git_sha in Reports | Empty in unified_report_20261110_210732.md (lines 50, 77, 100, 124, 145, 190) | Fix build_run_provenance.py to populate git_sha |
| Integration Latency | Component benchmark shows 0.0007s mean (contract-only measurement) | Fix integration benchmark to measure end-to-end execution time |
| Vietnamese/English Retrieval Gap | Not measured; Phase 5 environmental blocker | Run semantic vs keyword comparison on Vietnamese queries when credentials available |
| MockAgentRunner | Phase E skipped; still in place for multi-turn | Replace with RealAgentRunner when real LLM evaluation unblocked |
| Opik Integration | PoC only; no live server or span instrumentation | Deploy Opik and add @opik.track decorators |

---

## 3. Renamed/Moved/Changed Terms and Paths

| Old Term/Path | New Term/Path | Change Type |
|---------------|---------------|-------------|
| package/agents/plan_executor.py | package/agents/planner/plan_executor.py | Moved to planner/ subdir |
| package/agents/type1_agent.py | package/agents/type1/type1_agent.py | Moved to type1/ subdir |
| package/tools/embeddings/ (NOT IMPLEMENTED) | package/embeddings/ (optional primitives) | Clarified status |
| package/evaluation/doubles/ (test doubles) | tests/agents/fakes/ (ScriptedLLM, ScriptedJudge, Fake*Tool) | Relocated to tests/ |
| campaign/ (duplicated in evaluation/) | Single package/evaluation/campaign/ | Fixed documentation error |
| tools/utils/ | Does NOT exist; use package/utils/ | Fixed documentation error |
| tool_selection_accuracy: low | tool_selection_accuracy: 0.4904 | Quantified with evidence |
| grounding_rate: 0.0 | grounding_rate: 0.6714 | Corrected with evidence |
| reflection_rescued: 0.0 | NOT measured in executor benchmark | Clarified benchmark scope |
| Phase 8 complete | Phases 9, 10, 10.1 complete | Added to phase table |
| 368 tests | 1696 tests collected | Updated test count |
| MockAgentRunner in evaluation/ | MockAgentRunner in tests/ (Phase E skipped) | Clarified location |
| Component benchmarks: 5 TODO | 6 implemented (5 + multi_turn) | Updated status |
| Campaign runner: unverified | Verified with campaign_001 artifacts | Evidence-based |
| resource/: missing | Exists at src/resource/ | Corrected |
| Future work: all pending | 3 items DONE (benchmarks, multi-turn, campaign) | Updated status |
| chua co artifact xac nhan | Added for 19 unverified claims | New notation |

---

## Verification Checklist

All file/class/script paths mentioned in the updated document have been verified to exist:

- package/agents/planner/plan_executor.py
- package/agents/type1/type1_agent.py
- package/tools/retrieval/search_tool.py (SearchTool)
- package/tools/sql/filter_tool.py (FilterTool)
- package/tools/ranking/similar_tool.py (SimilarTool)
- package/tools/ranking/rank_tool.py (RankTool)
- package/tools/sql/lookup_tool.py (LookupTool)
- package/memory/memory_tool.py (MemoryTool)
- package/inference/compose/compose_llm.py
- package/inference/compose/compose_template.py
- package/inference/grounding/check_grounding.py
- package/embeddings/__init__.py (and encoder.py, text_encoder.py, vector_store.py)
- configs/agent/*.yaml (11 files)
- scripts/data_pipeline/run_pipeline.py
- scripts/evaluation/run_agent_eval.py
- scripts/evaluation/run_campaign.py
- scripts/evaluation/run_component_benchmarks.py
- scripts/evaluation/ranking_eval.py
- scripts/evaluation/candidate_recall.py
- scripts/evaluation/semantic_candidate_eval.py
- scripts/evaluation/jev_smoke_test.py
- scripts/demo/run_demo.py
- scripts/tools/run_tools.py
- scripts/experiments/compare_experiments.py
- scripts/llm_agent/smoke_real_llm.py
- scripts/eda_diagnostic/run_eda.py
- scripts/eda_diagnostic/diagnose_splits.py
- src/resource/ directory with all pipeline artifacts
- experiments/agent_eval/campaigns/campaign_001/campaign_001_summary.md
- experiments/agent_eval/component_benchmarks/unified_report_20261110_210732.md

Branch/Commit/Test verification:
- Branch: tools-building (git rev-parse --abbrev-ref HEAD)
- Commit: 880bf5c (git log --oneline -1)
- Tests: 1696 collected (pytest --collect-only -q)
- Working tree: 1 modified, 7 untracked (git status --short)
