# Phase 4 — remaining items (4.1–4.6, after 4.7)

Date: 2026-11-09. All six remaining Phase 4 items implemented.

## 4.1 Campaign statistical_settings → bootstrap/CI

- `campaign_runner._compare_experiments` now reads `statistical_settings`
  (confidence_level, bootstrap_samples, paired_comparison, optional
  random_seed) from campaign.yaml — previously dead config.
- Per metric: `metric_stats[metric][a|b]` = mean/std/bootstrap-CI/n across
  repeated runs; when `paired_comparison` and run counts match,
  `paired_bootstrap_difference` adds `delta_ci`, `p_value`, `significant`.
- Uses `evaluation/statistics/_bootstrap.py` (numpy). NOT merged with
  `ablation/_statistics.py` — different semantics (run-level vs per-case
  paired diffs + McNemar); documented in code comment.
- Tests: `test_statistical_settings_produce_ci_and_paired_delta`,
  `test_unpaired_or_disabled_statistics_skip_delta_ci` (22 campaign tests pass).

## 4.2 Integration benchmark — real boundary

- Rewrote `integration_benchmark.py`: was self-referential dict validation;
  now runs the REAL chain `PlanExecutor._execute` (real fixture tools) →
  `outcome_from_plan_results` → `compose_answer` (mode="template" default,
  deterministic, no LLM; "llm" via config).
- Dataset rewritten: 35 synthetic → 12 real cases (success, refs, empty,
  tool_error, invented_id, partial failure, edge).
- Metrics split honestly: `contract_valid` (status + item shape),
  `no_mismatch` (answer items ⊆ executed-step items — real provenance check),
  `grounded_rate`.
- Verified: 12/12, all metrics 1.0000. One expectation corrected after real
  run: bad $ref path with surviving FilterTool → status "ok" partial (real
  behavior, not tool_error).

## 4.3 Grounding benchmark — real inference output

- Replaced hand-written answer sentences with real `AgentOutcome` →
  `compose_answer` output (template mode; "llm" via config).
- `evidence_kind`: `synthetic_answer_judge_only` → `real_inference_output`;
  added `answer_composer`/`answer_mode`/`answer_status` fields.
- Jev evaluation unchanged (still requires TYPESAFE_API_KEY; failures fail
  cases). Stale test label updated.

## 4.4 Multi-turn — real runner + no placeholder metrics

- New `_agent_runner.py`: `RealAgentRunner` = PlanExecutor + Session +
  `for_planner_memory` tools + real LLM (requires LLM_BASE_URL; raises
  loudly otherwise). `run_turn` returns items (namespaced ids), exclusions
  extracted from executed FilterTool args, usage, trace.
- `_run.py` CLI wired: loads conversations.jsonl, evaluates, writes summary
  JSON to `data_paths.outputs.multi_turn` (previously dead config key — now
  live).
- Placeholder metrics fixed in `multi_turn_evaluator.py`:
  - `reference_correctness`: real check — fraction of $ref steps without
    bad_reference/invented_id errors; `None` when no refs (was always 1.0).
  - `context_retention`: monotonic shown_items growth, `None` for <2 turns
    (was always 1.0).
  - `reference_accuracy`/aggregates skip `None` instead of defaulting.
  - `item_match_rate` compares bare ASIN (dataset "vg_a" vs runtime
    "Video_Games::vg_a").
- Verified: 32 multi-turn tests pass; CLI fails loudly without LLM creds
  (correct — no fake scores).

## 4.5 Benchmark provenance

- `run_benchmark_cli.py`: `metadata.provenance` = component, dataset,
  `evaluator_config_sha256`, plus `llm` (provider/model/base_url_sha256/
  config_sha256) for planner and `judge` (model/config_sha256) for grounding.
- `_scrub_secrets` redacts key/secret/token/password/credential values
  before hashing; `metadata.config` also scrubbed (no raw secrets in JSON).
- 5 new tests in `test_provenance.py`.

## 4.6 Path fixes

- `planner_benchmark.py`: CWD-relative `configs/agent/llm.yaml` manual parse →
  `load_config("agent/llm")` (root-anchored + env expansion).
- `run_campaign.py`: `DEFAULT_CAMPAIGN_CONFIG` anchored to repo ROOT.
- `_run_all.py` + `component_benchmarks.yaml` + `_schemas.py`: component→
  dataset map moved into YAML (`datasets:`), schema field added
  (extra=forbid safe).

## Verification

- `pytest tests/ -q`: **1395 passed, 2 xfailed** (was 1388; +5 provenance,
  +2 campaign stats).
- Executor benchmark: 18/18 real cases, metrics 1.0.
- Integration benchmark: 12/12 real boundary cases, metrics 1.0.
- Multi-turn CLI without creds: honest ValueError, exit 1.

## Files changed

- campaign_runner.py, _bootstrap consumers; integration_benchmark.py +
  integration_dataset.jsonl; grounding_benchmark.py; multi_turn/
  (_agent_runner.py new, _run.py, multi_turn_evaluator.py);
  run_benchmark_cli.py; planner_benchmark.py; run_campaign.py;
  _run_all.py; _schemas.py; component_benchmarks.yaml; repo reading.md;
  tests: test_campaign.py (+2), test_provenance.py (new),
  test_grounding_phase1.py (label update).

## Remaining gaps (honest)

- Planner/grounding/multi-turn real runs still need LLM/Jev credentials —
  code is real, execution unverified in this environment.
- Integration benchmark uses template compose mode by default; "llm" mode
  available via config.
- Multi-turn `exclusion_compliance` depends on runner surfacing filter args;
  session.constraints path not yet wired into scoring.
