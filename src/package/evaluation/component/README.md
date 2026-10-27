# Component-Level Evaluation Framework

Framework for benchmarking individual components (Memory, Planner, Executor, Reflection, Inference, Grounding) independently from end-to-end evaluation.

## Overview

This framework provides:

- **Schema definitions** for benchmark cases, results, and regression reports
- **Dataset loader** for loading test cases from JSON/JSONL files
- **Base evaluator interface** for component-specific evaluators
- **CLI runner** for executing benchmarks
- **Regression analysis** for comparing benchmark runs
- **Tag-based filtering** for organizing test cases

## Architecture

```
package/evaluation/component/
├── __init__.py
├── _schema.py          # Dataclass schemas (BenchmarkCase, BenchmarkResult, BenchmarkSummary, RegressionReport)
├── _loader.py          # Dataset loader (load_cases, save_cases, filter_cases_by_tag, filter_cases_by_metadata)
├── _evaluator.py       # Base ComponentEvaluator class
├── _regression.py      # Regression analysis (compare_benchmarks, format_regression_report)
├── run.py              # CLI runner
└── benchmarks/
    ├── __init__.py
    ├── memory_benchmark.py       # MemoryTool evaluator
    └── dummy_memory_dataset.jsonl  # Example dataset
```

## Quick Start

### 1. Run the dummy MemoryTool benchmark

```bash
cd src
python -m package.evaluation.component.run \
    --component memory \
    --dataset package/evaluation/component/benchmarks/dummy_memory_dataset.jsonl \
    --runs 1
```

This will:
- Load 3 test cases from the dataset
- Run MemoryTool on each case
- Score the results against expected outputs
- Save results to `memory_benchmark_<timestamp>.json`

### 2. Compare two benchmark runs (regression analysis)

```bash
python -m package.evaluation.component.run regress \
    --baseline memory_benchmark_20261026_173532.json \
    --current memory_benchmark_current.json \
    --text-report regression_report.txt
```

This will:
- Load baseline and current benchmark results
- Compare metrics and latency
- Generate a JSON report and a human-readable text report

## Dataset Format

Benchmark datasets are JSON or JSONL files with the following structure:

### JSON format

```json
[
  {
    "case_id": "memory_001",
    "input": {
      "user_id": "u1",
      "top_n_categories": 2
    },
    "expected": {
      "user_id": "u1",
      "known": true,
      "n_interactions": 3,
      "top_categories": ["Action", "Puzzle"],
      "price_range": {"min": 1.0, "max": 300.0},
      "recent_items": ["Video_Games::vg_c", "Video_Games::vg_b", "Video_Games::vg_a"]
    },
    "tags": ["normal"],
    "metadata": {
      "description": "Normal user with 3 interactions"
    }
  }
]
```

### JSONL format (recommended)

```jsonl
{"case_id": "memory_001", "input": {"user_id": "u1"}, "expected": {"known": true}, "tags": ["normal"]}
{"case_id": "memory_002", "input": {"user_id": "unknown"}, "expected": {"known": false}, "tags": ["negative", "cold_start"]}
```

### Tags

Tags are used for categorization and filtering:
- `normal`: Standard cases
- `hard`: Difficult/edge cases
- `ambiguous`: Cases with ambiguous input
- `negative`: Negative/cold-start cases
- `oracle`: Cases with oracle data

## Creating a Component Evaluator

To create a benchmark for a new component:

1. **Subclass ComponentEvaluator**:

```python
from package.evaluation.component._evaluator import ComponentEvaluator
from package.evaluation.component._schema import BenchmarkCase
from typing import Any

class MyComponentEvaluator(ComponentEvaluator):
    def run_component(self, case_input: dict[str, Any]) -> dict[str, Any]:
        """Run your component with the given input."""
        # Your component logic here
        return {"result": "output"}

    def score_component(self, actual_output: dict[str, Any], expected: dict[str, Any]) -> dict[str, float]:
        """Score the actual output against expected."""
        # Return dict of metric names to values
        return {"accuracy": 1.0 if actual_output == expected else 0.0}
```

2. **Register in run.py**:

Edit `package/evaluation/component/run.py` to add your component to `_get_evaluator()`:

```python
def _get_evaluator(component: str, config: dict[str, Any]):
    if component == "memory":
        from .benchmarks.memory_benchmark import MemoryEvaluator
        # ... setup ...
        return MemoryEvaluator(...)
    elif component == "my_component":
        from .benchmarks.my_component_benchmark import MyComponentEvaluator
        # ... setup ...
        return MyComponentEvaluator(...)
    else:
        raise NotImplementedError(...)
```

3. **Create a dataset**:

Create a JSONL file with test cases for your component.

4. **Run the benchmark**:

```bash
python -m package.evaluation.component.run \
    --component my_component \
    --dataset path/to/dataset.jsonl \
    --runs 1
```

## CLI Reference

### Run benchmark

```bash
python -m package.evaluation.component.run \
    --component <name> \
    --dataset <path> \
    [--runs <n>] \
    [--output <path>] \
    [--tags <tag1> <tag2> ...] \
    [--metadata <key=value> ...] \
    [--config <path>] \
    [--git-sha <sha>]
```

Arguments:
- `--component`: Component name (required)
- `--dataset`: Path to dataset file (required)
- `--runs`: Number of times to run each case (default: 1)
- `--output`: Path to save results (default: auto-generated)
- `--tags`: Filter cases by tags (OR logic)
- `--metadata`: Filter cases by metadata (format: key=value, AND logic)
- `--config`: Path to JSON config file
- `--git-sha`: Git commit SHA (auto-detected if not provided)

### Regression analysis

```bash
python -m package.evaluation.component.run regress \
    --baseline <path> \
    --current <path> \
    [--output <path>] \
    [--metric-threshold <float>] \
    [--latency-threshold <float>] \
    [--text-report <path>]
```

Arguments:
- `--baseline`: Path to baseline results (required)
- `--current`: Path to current results (required)
- `--output`: Path to save JSON report (default: auto-generated)
- `--metric-threshold`: Threshold for significant metric change (default: 0.05 = 5%)
- `--latency-threshold`: Threshold for significant latency change (default: 0.1 = 10%)
- `--text-report`: Path to save human-readable text report

## Result Schema

### BenchmarkSummary

```json
{
  "benchmark_version": "1.0.0",
  "component": "memory",
  "config": {},
  "prompt_schema_hash": null,
  "run_count": 1,
  "per_case_results": [
    {
      "case_id": "memory_001",
      "actual_output": {...},
      "success": true,
      "error": null,
      "metrics": {
        "known_correct": 1.0,
        "n_interactions_correct": 1.0,
        ...
      },
      "latency_seconds": 0.001,
      "token_usage": null
    }
  ],
  "metrics": {
    "known_correct_mean": 1.0,
    "known_correct_std": 0.0,
    "success_rate": 1.0,
    ...
  },
  "latency": {
    "mean": 0.0005,
    "p50": 0.0003,
    "p95": 0.0011,
    ...
  },
  "token_cost": null,
  "timestamp": "2026-10-26T17:35:32.990485",
  "git_sha": "eec93f54b2870c6496b2fd7c40502a6dea97f599",
  "tags_summary": {
    "normal": {...},
    "negative": {...}
  }
}
```

### RegressionReport

```json
{
  "baseline_summary": {...},
  "current_summary": {...},
  "metric_changes": {
    "success_rate": {
      "baseline": 0.9,
      "current": 0.95,
      "delta": 0.05,
      "percent_change": 5.56,
      "significant": true
    }
  },
  "latency_changes": {
    "mean": {
      "baseline": 0.5,
      "current": 0.6,
      "delta": 0.1,
      "percent_change": 20.0,
      "significant": true
    }
  },
  "tag_changes": {...},
  "summary": "improved",
  "timestamp": "2026-10-26T17:35:44.963003"
}
```

## Best Practices

1. **Dataset organization**:
   - Use JSONL format for large datasets
   - Include descriptive metadata for each case
   - Use tags to categorize cases (normal, hard, negative, etc.)
   - Keep oracle data separate from real user queries

2. **Metric design**:
   - Include multiple metrics per component (not just a single score)
   - Use 0-1 scale for binary metrics
   - Track both success/failure and quality metrics
   - Include latency metrics for performance monitoring

3. **Regression testing**:
   - Run benchmarks before and after changes
   - Use appropriate thresholds for your use case
   - Review tag-based changes to understand impact on specific case types
   - Save regression reports for documentation

4. **CI integration**:
   - Add benchmark runs to CI pipeline
   - Use regression analysis to detect performance degradation
   - Fail CI if key metrics regress beyond threshold

## Current Status

- ✅ Framework implemented
- ✅ MemoryTool benchmark (dummy example)
- ✅ CLI runner with filtering support
- ✅ Regression analysis
- ✅ Unit tests for loader and regression
- ⏳ Planner/Executor benchmarks (to be implemented)
- ⏳ Reflection benchmark (to be implemented)
- ⏳ Inference/Grounding benchmarks (to be implemented)

## Related Documentation

- [Component Evaluation Inventory](../../../../docs/evaluation/inventory.md) - Detailed inventory of existing evaluation infrastructure
- [EVALUATION_PROTOCOL.md](../../../../EVALUATION_PROTOCOL.md) - End-to-end evaluation protocol
- [Evaluation layer documentation](../) - End-to-end evaluation layers (layer1→layer5)

## Limitations

- Framework does not automatically generate test cases - these must be hand-crafted
- Component-specific evaluators must be implemented for each component
- Currently only MemoryTool has a benchmark implementation
- Regression thresholds are fixed per run (not adaptive)

## Future Work

- Implement benchmarks for Planner, Executor, Reflection, Inference, Grounding
- Add automatic test case generation from held-out data
- Implement adaptive regression thresholds
- Add CI integration examples
- Create visualization tools for benchmark results
