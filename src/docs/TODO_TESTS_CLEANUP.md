# TODO: tests/ cleanup (deferred from Phase 10)

Phase 10 removed all fake/mock/offline code from `package/` and `scripts/`. Test fakes were left in place and only minimally repointed. This document lists the deferred cleanup work for `tests/` — do NOT start until Phase 10 is fully merged.

## 1. One home and one copy for test fakes

Duplicated doubles currently living in `tests/`:

- `ScriptedLLM` defined inline in **2** places (in addition to `tests/agents/fakes/scripted_llm.py`)
- `MockRecommender` defined in **2** places (`tests/recommenders/test_base_recommender.py`, `tests/tools/evaluation/test_evaluator.py`)
- `FakeScorer` (`tests/tools/ranking/test_ranking_hardening.py`)
- `FakeModel` (`tests/scoring/test_contract_baseline_scorer.py`)
- `tests/agents/fakes/` already has `Fake*Tool` ×6 + `ScriptedLLM` + `sample_data.py`

Target: single `tests/fakes/` (or keep `tests/agents/fakes/` and repoint), one copy each, contract tests covering every fake.

## 2. tests/ should mirror package/ layout

Misplaced test homes:

- inference/memory/api/recommender tests currently under `tests/agents/` (e.g. `tests/agents/inference/`, `tests/agents/test_memory_tool.py`, `tests/agents/test_llm_provider.py`)
- `test_eval_helpers` under `tests/data/`
- stale test names under `tests/tools/ranking/` (files testing `tools/evaluation` or scoring living under ranking)

Target: `tests/<package-area>/` mirroring `package/` structure.

## 3. Architecture/layout tests

- Move the 4 layout tests (`test_package_layout.py`, `test_dependency_direction.py`, `test_import_resolution.py`, `test_path_hygiene.py`) into a dedicated `tests/architecture/` (or `tests/config/` stays — decide).
- Place `tools_helpers.py` and `results_report.py` properly (currently loose under tests helpers).
- Make `run_tests` scripts consistent (multiple variants exist).

## 4. Contract tests for fakes

- Fake contract tests covering **every** fake (tools, LLM, judge, recommender, scorer, model).
- The failing-tool regression test (`ToolResult.ok is False`) currently lives in `tests/evaluation/component/benchmarks/test_controlled_tools.py` using relocated `Controlled*Tool` copies — re-home it next to the canonical fake it should cover.
- Executor benchmark failure-injection scenarios (deleted from `package/` in Phase 10.1 Step 5) should be re-expressed as pytest tests using `tests/` fakes.

## 5. Private-import exceptions in `tests/config/test_package_layout.py`

`PRIVATE_IMPORT_EXCEPTIONS` still lists 7 cross-folder private imports that are real violations to fix properly (not test fakes):

- `package/corpus/build_corpus.py` → `package.data._schema`
- `package/corpus/item_corpus.py` → `package.data._schema`
- `package/demo/backend/live_backend.py` → `package.data._shared.select_fit_target`
- `package/evaluation/recommender/config/__init__.py` → `package.data._shared.select_fit_target`
- `package/evaluation/recommender/config/segment_users_by_history.py` → `package.evaluation.recommender.core._helper`
- `package/evaluation/recommender/experiment/save_experiment.py` → `package.evaluation.recommender.core._helper`
- `package/tools/_schema.py` → `package.data._schema`

Each needs either a public re-export or a deliberate architecture decision, then the exception entry removed.
