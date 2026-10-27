# Planner Benchmark - Guide

## Overview

Planner benchmark evaluates the PlanExecutor component in isolation using mock tools and mock LLM.

## Running the Benchmark

```bash
python -m package.evaluation.component.run \
    --component planner \
    --dataset package/evaluation/component/benchmarks/planner_dataset.jsonl \
    --runs 1
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

### 2. Update mock LLM (if needed)

Edit `planner_mock_llm.py` to add a pattern for the new request:

```python
return MockLLMProvider({
    "your request pattern": {
        "text": '{"steps": [{"tool": "ToolName", "args": {"key": "value"}}]}'
    }
})
```

### 3. Run benchmark

```bash
python -m package.evaluation.component.run \
    --component planner \
    --dataset package/evaluation/component/benchmarks/planner_dataset.jsonl \
    --runs 1
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

- Mock LLM only matches exact patterns
- Small sample size (4 cases)
- No real LLM support yet
- No stability testing (N runs)

## Future Work

- Increase sample size
- Add rule-based oracle
- Support real LLM
- Add stability testing
- Deep reference resolution testing
