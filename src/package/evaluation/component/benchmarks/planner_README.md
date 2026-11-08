# Planner Benchmark - Guide

## Overview

Planner benchmark evaluates the PlanExecutor component in isolation using a real LLM and real tools built over the synthetic fixture corpus (`fixtures/create_test_*`).

Requires `LLM_BASE_URL` / LLM credentials (see `configs/agent/llm.yaml`); the benchmark fails fast if they are missing.

## Running the Benchmark

```bash
python -m package.evaluation.component.run \
    --component planner \
    --dataset package/evaluation/component/benchmarks/planner_dataset.jsonl
```

## Adding New Test Cases

### 1. Add case to dataset

Edit `planner_dataset.jsonl` and add a new line:

```json
{
  "case_id": "planner_005",
  "input": {"user_request": "Your test request here"},
  "expected": {
    "steps": [
      {"tool": "ToolName", "args": {"key": "value"}}
    ],
    "question": null
  },
  "tags": ["planner", "normal"],
  "metadata": {"description": "Description of this case"}
}
```

`expected.steps` must use the real tool names (`SimilarTool`, `RankTool`, `LookupTool`, `SearchTool`, `FilterTool`) and the argument shapes those tools actually accept.

### 2. Run benchmark

```bash
python -m package.evaluation.component.run \
    --component planner \
    --dataset package/evaluation/component/benchmarks/planner_dataset.jsonl
```

## Tags

- `normal`: Simple, straightforward requests
- `hard`: Multi-step, references, complex constraints
- `ambiguous`: Missing information, should ask clarification
- `must-not-guess`: Unknown user/item, should not guess

## Metrics

- `tool_selection_accuracy`: Tool selection correctness
- `argument_correctness`: Argument field match
- `plan_validity`: Plan is valid list of steps
- `reference_correctness`: $N.path reference correctness
- `constraint_handling`: Constraint in filters
- `clarification_precision`: Ask when needed
- `clarification_recall`: Ask appropriately
- `refusal_to_guess`: Don't guess when unknown

## Limitations

- Real LLM output is non-deterministic; scores vary between runs
- Small sample size
- Fixture corpus is synthetic (memory-benchmark fixtures), not production data

## Future Work

- Increase sample size
- Add rule-based oracle
- Add stability testing (N runs)
- Deep reference resolution testing
