# Execution, Resume, Compare, and Export Guide

This document explains how to execute evaluations, resume interrupted runs, compare results, and export data.

## Execution

### Single-Turn Evaluation

#### Component Benchmarks
```bash
# Run a specific component benchmark (run count + evaluator config from
# configs/eval/component_benchmarks.yaml; output from data_paths.outputs.component_benchmarks)
python -m package.evaluation.component.run \
    --component planner \
    --dataset <path-to-dataset.jsonl>

# Run all component benchmarks
python -m package.evaluation.component._run_all
```

#### End-to-End Evaluation
End-to-end agent evaluation runs via `scripts/evaluation/run_agent_eval.py`
(operational selectors only; all tunables in `configs/agent/*.yaml` — see RUN_SCRIPTS.md).

### Multi-turn Evaluation
```bash
python -m package.evaluation.multi_turn._run \
    --dataset package/evaluation/multi_turn/conversations.jsonl
# results -> data_paths.outputs.multi_turn/conversation_results_<ts>.json
```

### Campaign Execution
```bash
# Programmatic (Python)
from package.evaluation.campaign import CampaignConfig, CampaignRunner

campaign = CampaignConfig.from_yaml("campaign.yaml")
runner = CampaignRunner(campaign, git_sha="abc123")
result = runner.run_campaign()
```

## Resume Functionality

### Component Benchmarks
Component benchmarks can be resumed by re-running with the same configuration. Results are written to timestamped files, so interrupted runs can be restarted without losing previous results.

### Campaign Checkpoint/Resume
```python
from package.evaluation.campaign import CheckpointManager

# Create checkpoint manager
manager = CheckpointManager(output_dir)

# Save checkpoint after each experiment
manager.save_checkpoint(result)

# Resume from checkpoint
checkpoint = manager.load_checkpoint()
if checkpoint:
    # Check which experiments are already completed
    completed_runs = [r.experiment_name for r in checkpoint.runs]
    # Run only remaining experiments
    ...
```

### Experiment Persistence
- Component benchmarks: Results saved to timestamped JSON files
- Campaigns: Checkpoint saved to `campaign_checkpoint.json`
- Full result saved to `campaign_result.json`
- Provenance tracked in `config.yaml` within each experiment directory

## Comparison

### Component Regression
```python
from package.evaluation.component._regression import compare_benchmarks

# Compare current run with baseline
baseline_path = "experiments/agent_eval/component_benchmarks/baseline/planner.json"
current_path = "experiments/agent_eval/component_benchmarks/current/planner.json"

report = compare_benchmarks(baseline_path, current_path)
# Returns: RegressionReport with metric deltas and improvement summary
```

### Campaign Comparison
Campaign comparisons are defined in the campaign YAML:
```yaml
comparison_pairs:
  - ["baseline", "improved_planner"]
  - ["baseline", "improved_memory"]
```

The campaign runner automatically computes:
- Metric deltas (absolute and relative)
- Statistical significance (if configured)
- Paired comparisons (if same cases used)

### Statistical Comparison
```python
from package.evaluation.statistics import (
    paired_bootstrap_difference,
    significance_test,
)

# Paired bootstrap CI
mean_diff, lower, upper, p_value = paired_bootstrap_difference(
    values_a, values_b,
    confidence_level=0.95,
    n_bootstrap=1000,
)

# Significance test
result = significance_test(
    values_a, values_b,
    test_type="paired",
    alpha=0.05,
)
```

## Export

### Markdown Reports
```python
from package.evaluation.reporting import generate_markdown_report

generate_markdown_report(
    results=evaluation_results,
    output_path="experiments/agent_eval/report.md",
    include_confidence_intervals=True,
    confidence_level=0.95,
)
```

### CSV Exports
```python
from package.evaluation.reporting import generate_csv_export

generate_csv_export(
    results=evaluation_results,
    output_path="experiments/agent_eval/data.csv",
)
```

### Failure Reports
```python
from package.evaluation.reporting import generate_failure_report

generate_failure_report(
    failures=failed_cases,
    output_path="experiments/agent_eval/failures.md",
)
```

### Comparison Reports
```python
from package.evaluation.reporting import generate_comparison_report

generate_comparison_report(
    comparison=comparison_result,
    output_path="experiments/agent_eval/comparison.md",
)
```

### Visualizations
```python
from package.evaluation.reporting import generate_all_charts

charts = generate_all_charts(
    results=evaluation_results,
    output_dir="experiments/agent_eval/charts",
)
```

## Provenance Tracking

Every evaluation run includes:
- **Git SHA**: Commit hash of code version
- **Source Fingerprint**: Hash of implementation files
- **Environment Versions**: Python, numpy, pandas, scipy, etc.
- **Hardware Info**: CPU, memory details
- **Timestamp**: ISO timestamp
- **Random Seed**: For reproducibility
- **Dataset Version**: Dataset hash or version

## Output Structure

### Component Benchmarks
```
experiments/agent_eval/component_benchmarks/
├── planner_20261102_120000.json
├── executor_20261102_120001.json
├── grounding_20261102_120002.json
├── integration_20261102_120003.json
└── memory_correctness_20261102_120004.json
```

### Campaigns
```
experiments/agent_eval/campaigns/campaign_001/
├── campaign.yaml
├── campaign_result.json
├── campaign_checkpoint.json
├── baseline/
│   ├── run_1/
│   │   ├── config.yaml
│   │   ├── metrics.json
│   │   └── traces.jsonl
│   ├── run_2/
│   └── run_3/
├── improved_planner/
│   ├── run_1/
│   ├── run_2/
│   └── run_3/
└── reports/
    ├── campaign_summary.md
    └── comparisons/
```

## Best Practices

1. **Reproducibility**: Always use the same random seed for comparable runs
2. **Provenance**: Check git SHA and source fingerprint before comparing results
3. **Backup**: Never delete historical experiment results
4. **Checkpoint**: Use checkpoint/resume for long-running campaigns
5. **Validation**: Validate results with smoke tests before full runs
6. **Documentation**: Include description and purpose in campaign metadata
