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

Known debt (tracked separately): campaign reporting consumes a `"multi_turn"`
key, Opik tracing is minimal, and some eval CLIs still have untested
`main()` paths.
