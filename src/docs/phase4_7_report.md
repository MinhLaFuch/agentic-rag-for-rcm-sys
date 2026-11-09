# Phase 4.7 — Executor benchmark rebuild (D1 option 1)

Date: 2026-11-09. Scope: rebuild the executor component benchmark with real
execution and move fault-injection scenarios to unit tests, per the approved
D1 decision (option 1).

## Case classification (old 35-case `executor_dataset.jsonl`)

Recovered from git history (`89116e8~1`). Every case's `tool_config` key was a
fault-injection switch (`sql_fail`, `sql_timeout`, `sql_rate_limit`,
`sql_network_error`, `sql_auth_error`, `sql_schema_error`, `sql_data_error`,
`sql_concurrent_error`, `sql_resource_error`, `sql_validation_error`,
`sql_permission_error`, `sql_generic_error`, `sql_random_error`,
`sql_malformed`, `sql_empty`, `sql_partial`, `itemcf_fail`, `itemcf_empty`,
`reflection_*`). The old `executor_benchmark.py` was additionally broken: it
read `should_fail`/`should_timeout`/`should_return_empty` keys that do not
exist in the dataset, and called an unimported `get_controlled_tools`.

| Old cases | Class | Disposition |
|---|---|---|
| 001, 006, 035 (plain FilterTool success) | real-reproducible | → new dataset exec_001/006 |
| 002, 010, 012, 014, 016, 018, 024, 026, 028, 030, 034 ($N.candidates refs) | partially real | ref mechanics → exec_005/007/008/009/010; "rescue" halves needed injected errors → unit tests |
| 004 (empty→reflect rescue), 007 (itemcf empty) | reproducible trigger, injected rescue | → exec_004 (empty result, no reflection) + unit test |
| 005 ($2.candidates broken ref) | real-reproducible | → exec_008/009 |
| 003, 008, 009, 013, 015, 017, 019–023, 025, 027, 029, 031–033 (infra errors: timeout, rate limit, network, auth, schema, data, concurrent, resource, validation, permission, generic, random, malformed) | fault-injection only | → `tests/agents/test_executor_error_taxonomy.py` (parametrized, 13 error labels) |
| 011, 012 ("partial results") | not a real tool behavior | dropped — FilterTool returns ok or ok=False, no partial mode |

Key finding: PlanExecutor cannot distinguish infra error *texts* — every
`ToolInputError`/ok=False becomes `error_kind="tool_error"` and triggers
reflection identically (only time-budget errors and invented ids are blocked
by `_blocks_reflect`). The taxonomy therefore adds no benchmark signal; it is
covered once, parametrized, in unit tests.

## Real benchmark (new)

- `package/evaluation/component/benchmarks/executor_benchmark.py` — builds the
  same real fixture tools as the planner benchmark (ItemKNN + BaselineScorer +
  `build_tools` over `create_test_*` fixtures) and calls
  `PlanExecutor._execute(steps, user_request)` directly. `llm=None` is
  intentional and documented: `_execute` never calls the LLM; plan/reflection
  are out of scope (planner benchmark covers real-LLM planning; reflection is
  covered by `test_plan_reflect.py`/`test_reflection_behavior.py` +
  `test_executor_error_taxonomy.py`).
- `executor_dataset.jsonl` — rewritten: 18 real cases (success, multi-step,
  `$N.path` refs incl. wildcard `.*`, forward/missing/bad-path/failed-step
  references, empty result, unknown tool, unknown args, bad arg type,
  invented id, unknown SimilarTool seed, missing LookupTool ids, SearchTool,
  empty plan). `evidence_kind: "real_execution"` in every result.
- Metrics: `all_steps_ok`, `step_success_rate`, `error_kind_accuracy`
  (per-step expected `error_kind`), `reference_resolution_ok`.

## Bug found and fixed by the real benchmark

Wildcard refs use dot syntax `$1.candidates.*.item_id` (`[*]` is not matched by
`_REF` and was misreported as `invented_id`). Separately, a bad *path* in a
valid ref (`$1.no_such_field`) produced `ValueError("... Step 1 ... not
found")` which `_execute` classified as `error_kind="exception"` instead of
`"bad_reference"` — the check required lowercase `"step"` but the message uses
`"Step"`. Fixed in `plan_executor.py:270` and `_helper.py:177`
(`_is_bad_reference`, previously dead code, aligned for consistency).
GitNexus impact: `_execute` HIGH (callers run_planner/main/eval — the change
only widens `bad_reference` classification for path errors; all agent tests
pass); `_is_bad_reference` UNKNOWN → grep confirmed no callers.

## Wiring

- `run_benchmark_cli.py`: added `executor` branch in `_get_evaluator`
  (impact: LOW, sole caller `run_benchmark_cli`).
- `configs/eval/component_benchmarks.yaml`: removed dead
  `executor.reflect_rounds` entry (benchmark needs no config).
- `_run_all.py`: no change needed — executor was already listed; it now runs
  for real instead of reporting `not_implemented`.

## Fault-injection coverage moved to tests

`tests/agents/test_executor_error_taxonomy.py` (29 tests): 13 infra-error
labels × (reflection triggers + rescue possible / rescue impossible),
exception-vs-tool_error distinction, time-budget blocks reflection, empty
result triggers reflection. Uses `tests/agents/fakes` (ScriptedLLM,
FakeFilterTool, `_FlakyFilterTool` for fail-then-succeed since tools are
keyed by name).

## Verification

```
$ python -m package.evaluation.component.run --component executor \
    --dataset package/evaluation/component/benchmarks/executor_dataset.jsonl
Loaded 18 cases → all_steps_ok_mean 1.0000, error_kind_accuracy_mean 1.0000,
reference_resolution_ok_mean 1.0000, step_success_rate_mean 0.6111
(expected: error cases legitimately fail steps), success_rate 1.0000, 18/18
```

```
$ pytest tests/agents/test_executor_error_taxonomy.py -q → 29 passed
$ pytest tests/agents/ tests/evaluation/component/ -q → 339 passed, 2 xfailed
$ pytest tests/ -q → 1388 passed, 0 skipped, 2 xfailed (was 1359; +29 new)
```

## Files changed

- new: `benchmarks/executor_benchmark.py`, `tests/agents/test_executor_error_taxonomy.py`, this report
- rewritten: `benchmarks/executor_dataset.jsonl` (35 fault-injection → 18 real)
- edited: `run_benchmark_cli.py` (+executor branch), `component_benchmarks.yaml` (−dead key),
  `plan_executor.py` (bad_reference case fix), `_helper.py` (`_is_bad_reference` align),
  `repo reading.md` (executor status + test counts)

## Remaining gaps

- Executor benchmark does not measure plan quality or reflection rescue with a
  real LLM — reflection with real LLM is unmeasured (planner benchmark covers
  planning; a future Phase 4 item could add an LLM-backed executor+reflect
  benchmark if desired).
- No thresholds configured for executor metrics yet (consistent with planner/
  grounding/integration pending real baselines).
