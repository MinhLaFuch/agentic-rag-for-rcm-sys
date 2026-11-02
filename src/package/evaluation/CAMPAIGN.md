# Campaign Configuration Documentation

This document explains how to configure and run campaign experiments for agent evaluation.

## Campaign YAML Schema

A campaign is defined in YAML with the following structure:

```yaml
campaign_id: "unique_campaign_id"
description: "Human-readable description"

dataset:
  path: "path/to/dataset.jsonl"
  version: "v1.0"
  split: "test"
  filters:
    domains: ["Video_Games"]

experiments:
  - name: "experiment_name"
    description: "Experiment description"
    agent_config:
      model: "gpt-4"
      provider: "openai"
      temperature: 0.0
      planner_type: "default"
      memory_enabled: true
    evaluation_config:
      layers: [1, 2, 3, 4, 5]
      request_kinds: ["similar", "personalized", "constrained"]
      metrics:
        - task_success_rate
        - grounded_answer_rate
    repetition_count: 3
    random_seed: 42
    tags: ["baseline"]

comparison_pairs:
  - ["experiment_a", "experiment_b"]
  - ["experiment_a", "experiment_c"]

statistical_settings:
  confidence_level: 0.95
  bootstrap_samples: 1000
  paired_comparison: true

output_dir: "experiments/agent_eval/campaigns/campaign_001"

metadata:
  author: "evaluation team"
  created: "2026-11-02"
  purpose: "Purpose description"
```

## Configuration Fields

### Campaign Level
- `campaign_id`: Unique identifier for the campaign
- `description`: Human-readable description
- `dataset`: Shared dataset configuration for all experiments
- `experiments`: List of experiment configurations (the matrix)
- `comparison_pairs`: List of (experiment_a, experiment_b) pairs to compare
- `statistical_settings`: Statistical comparison settings
- `output_dir`: Directory for campaign output
- `metadata`: Additional metadata

### Experiment Level
- `name`: Unique experiment name
- `description`: Experiment description
- `agent_config`: Agent configuration (model, provider, parameters)
- `evaluation_config`: Evaluation configuration (layers, request kinds, metrics)
- `dataset`: Optional dataset override for this experiment
- `repetition_count`: Number of times to repeat the experiment
- `random_seed`: Random seed for reproducibility
- `tags`: Tags for grouping/filtering

### Agent Config
- `model`: Model name (e.g., "gpt-4", "gpt-3.5-turbo")
- `provider`: Provider name (e.g., "openai", "anthropic")
- `temperature`: Sampling temperature
- `planner_type`: Planner variant (default, improved_v1, etc.)
- `memory_enabled`: Whether memory is enabled
- `memory_type`: Memory variant (if enabled)

### Evaluation Config
- `layers`: Evaluation layers to include (1-5)
- `request_kinds`: Request kinds to evaluate
- `metrics`: Metrics to compute

## Experiment Matrix Examples

### Baseline vs Improved
```yaml
experiments:
  - name: "baseline"
    agent_config:
      planner_type: "default"
  - name: "improved_planner"
    agent_config:
      planner_type: "improved_v1"
  - name: "improved_memory"
    agent_config:
      memory_type: "improved_v1"
  - name: "full_improved"
    agent_config:
      planner_type: "improved_v1"
      memory_type: "improved_v1"
```

### Ablation Study
```yaml
experiments:
  - name: "full_system"
    agent_config:
      planner_type: "improved"
      memory_enabled: true
  - name: "no_memory"
    agent_config:
      planner_type: "improved"
      memory_enabled: false
  - name: "no_reflection"
    agent_config:
      planner_type: "improved"
      memory_enabled: true
      reflection_enabled: false
```

### Configuration Variants
```yaml
experiments:
  - name: "temperature_0"
    agent_config:
      temperature: 0.0
  - name: "temperature_05"
    agent_config:
      temperature: 0.5
  - name: "temperature_1"
    agent_config:
      temperature: 1.0
```

## Statistical Settings

- `confidence_level`: Confidence level for CIs (default 0.95)
- `bootstrap_samples`: Number of bootstrap samples (default 1000)
- `paired_comparison`: Whether to use paired comparison (default true)

## Running Campaigns

### Programmatic
```python
from package.evaluation.campaign import CampaignConfig, CampaignRunner

# Load campaign config
campaign = CampaignConfig.from_yaml("campaign.yaml")

# Create runner
runner = CampaignRunner(campaign, git_sha="abc123")

# Run campaign
result = runner.run_campaign()

# Result includes:
# - runs: List of all experiment runs
# - comparisons: Comparison results between pairs
# - summary: Campaign summary statistics
```

### Checkpoint/Resume
```python
from package.evaluation.campaign import CheckpointManager

# Create checkpoint manager
manager = CheckpointManager(output_dir)

# Save checkpoint after each experiment
manager.save_checkpoint(result)

# Resume from checkpoint
checkpoint = manager.load_checkpoint()
if checkpoint:
    # Skip completed experiments
    resume_from_checkpoint = True
```

## Output Structure

```
experiments/agent_eval/campaigns/campaign_001/
├── campaign.yaml                    # Campaign configuration
├── campaign_result.json             # Full campaign result
├── campaign_checkpoint.json         # Checkpoint (if interrupted)
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
├── comparisons/
│   ├── baseline_vs_improved_planner.json
│   └── baseline_vs_full_improved.json
└── reports/
    ├── campaign_summary.md
    └── comparison_reports/
```

## Comparison Results

Each comparison includes:
- `status`: success or skipped
- `experiment_a`, `experiment_b`: Experiment names
- `runs_a`, `runs_b`: Number of runs for each
- `deltas`: Metric deltas (a, b, delta, relative_delta)
- `significance`: Statistical test results (if applicable)

## Best Practices

1. **Repetition Count**: Use at least 3 repetitions for statistical significance
2. **Random Seed**: Use the same seed across experiments for fair comparison
3. **Dataset Version**: Pin dataset version for reproducibility
4. **Comparison Pairs**: Compare systematically (baseline vs each improvement)
5. **Tags**: Use tags to group experiments (baseline, ablation, variant)
6. **Output Directory**: Use descriptive directory names for campaigns
