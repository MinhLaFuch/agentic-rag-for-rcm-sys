# Multi-turn conversation evaluation — first run

Evaluates planner+Session behavior across multi-turn conversations
(`package/evaluation/multi_turn/`). Requires a **real LLM**: the runner wraps
`PlanExecutor` + `Session` over the fixture corpus and fails loudly without
credentials — it never produces fake scores.

> **Status: chưa chạy thật.** The real end-to-end run (standalone CLI or via
> `_run_all`) has NOT been executed yet — it needs `LLM_BASE_URL`/`LLM_API_KEY`
> for a reachable OpenAI-compatible endpoint. All verification so far is
> offline unit tests with fakes/mocks at the test layer only.

## Prerequisites

- `LLM_BASE_URL` and `LLM_API_KEY` (resolved by `configs/agent/llm.yaml`), or
  an explicit `{"llm": {...}}` config passed to `RealAgentRunner`.
- Run from `src/` with the project on `PYTHONPATH` (same as other scripts).

## Standalone run

```bash
cd src
python -m package.evaluation.multi_turn._run \
    --dataset package/evaluation/multi_turn/conversations.jsonl
```

Options: `--git-sha <sha>` (auto-detected), `--output <path>` (default:
`data_paths.outputs.multi_turn/<dataset>_<ts>.json` →
`experiments/agent_eval/multi_turn/`).

The bundled dataset has 11 conversations covering price refinement, position
references, exclusions, and session carry-over (`conversations.jsonl`).

## Via component benchmarks (`_run_all`)

`python -m package.evaluation.component._run_all` runs multi-turn as an extra
report step after the component benchmarks:

- **LLM configured** → runs the CLI above, parses `Results saved to:` and
  aggregates `turn_success_rate`, `conversation_success_rate`, and
  `metrics` into the unified report (`status: success`,
  `quality_gate: not_evaluated` — there are no thresholds yet).
- **No LLM credentials** → the report shows
  `status: skipped_no_credentials` with `Skipped: N` in the summary. This is
  intentional and distinct from "not implemented" or a failure: the component
  is absent from scoring, not silently missing.

## Interpreting results

- `turn_success_rate` / `conversation_success_rate`: per-turn and whole-
  conversation success against `expected_items`, `expected_exclusions`, and
  `expected_tool_calls` in the dataset. NOTE: `turn_success_rate` only counts
  EXECUTED turns — turns after a failure never run, so an early failure makes
  it look optimistic. Always read it together with
  `conversation_success_rate` and `turn_completion_ratio`.
- `total_turns_scheduled` / `total_turns_executed` /
  `turn_completion_ratio` (= executed/scheduled): the "gave up early" signal.
  `avg_turns_per_conversation` is executed turns / conversations.
- `failed_conversation_ids` / `failed_conversations` / `failure_distribution`:
  which conversations failed and at which stage.
- `metrics.tool_call_match_rate`, `context_retention`, per-scenario metrics:
  see `ConversationSummary.metrics` in the output JSON.
- All of the above measure planner/session behavior on the **synthetic
  fixture corpus** (`create_test_*`), not recommendation quality on the real
  catalog — do not read them as real-data metrics.

## Via `run_agent_eval` / campaign (Phase B wiring)

`agent_eval.multi_turn` in `configs/agent/agent_eval.yaml` gates an optional
step that runs after the main agent eval:

- `enabled: false` (default) → nothing runs; `metrics.json`/`config.yaml`
  are byte-identical to before.
- `enabled: true`, `output_dir: null` → writes `multi_turn.json` into the
  experiment dir (`experiments/agent_eval/exp_NNN/`).
- `output_dir: <dir>` → writes `<dir>/multi_turn.json` instead — exactly one
  location, no copying. Relative dirs resolve under `experiments/`.
- Missing LLM credentials → the file records
  `{"status": "skipped_no_credentials", "reason": ...}`; no metrics are
  fabricated. An existing file with `status: "success"` is reused as-is
  (resume — the eval has no incremental state).

`exp_config` (config.yaml in the exp dir) records
`multi_turn: {enabled, status, output_path, dataset}` when the step ran.

Campaigns (`configs/evaluation/campaign.yaml` → `multi_turn: once|never`):

- `once` (default): the overlay enables multi-turn **only** for the first
  experiment's first repetition and points `output_dir` at
  `campaigns/<id>/multi_turn/` — the artifact lands there directly, never in
  an `exp_NNN/` dir.
- `campaign_result.json` gains a top-level `multi_turn` entry:
  `{status, path, metrics}` on success/skipped, `not_run` + reason when the
  first experiment failed before the step, `disabled` when `never`.
- Multi-turn metrics are **informational only** — they never enter paired
  experiment comparisons (different scale: fixture conversations vs real-data
  ranking metrics).
