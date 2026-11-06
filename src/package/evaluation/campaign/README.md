# Campaign Evaluation Framework

## Overview

The campaign framework orchestrates multiple agent evaluation experiments, automatically comparing results between different configurations. Supports both **explicit experiment lists** and **parameter grid search** for systematic hyperparameter tuning.

## Quick Start

### 1. Smoke Test (Dry Run)

Check what the campaign would run without actually executing:

```bash
cd src
PYTHONPATH=. python scripts/evaluation/run_campaign.py \
    --campaign-config package/evaluation/campaign/example_campaign.yaml \
    --dry-run
```

### 2. Run Full Campaign with Parameter Grid

Execute the campaign with real data using parameter grid search:

```bash
cd src
PYTHONPATH=. python scripts/evaluation/run_campaign.py \
    --campaign-config package/evaluation/campaign/example_campaign.yaml \
    --git-sha $(git rev-parse HEAD)
```

### 3. Run Small Test

To test with minimal data first, modify the YAML with small `per_segment` values:

```yaml
parameter_grid:
  agents:
    - ["baseline"]
  inference_mode:
    - "template"
  reflect_rounds:
    - 0
# Add this to each experiment (or use experiments list instead):
# evaluation_config:
#   per_segment: 2  # Very small for testing
```

## Campaign YAML Structure

### Option 1: Parameter Grid (Recommended for Systematic Search)

Auto-generate all combinations of parameters:

```yaml
campaign_id: "campaign_001_parameter_grid"
description: "Parameter grid search: agents x inference_mode x reflect_rounds"

dataset:
  tag: "default"
  split: "validation"
  filters:
    domains: ["Video_Games"]

# Parameter grid: auto-generate all combinations
# This creates 3 agents x 2 inference_modes x 2 reflect_rounds = 12 experiments
parameter_grid:
  agents:
    - ["baseline", "type1"]  # Baseline agents
    - ["planner"]            # Planner only
    - ["planner_memory"]     # Planner with memory
  inference_mode:
    - "template"  # No LLM for answer (deterministic)
    - "llm"       # LLM for answer (slower)
  reflect_rounds:
    - 0  # No reflection
    - 2  # 2 reflection rounds

# Optional: Add per_segment (applies to all experiments)
evaluation_config:
  per_segment: 20  # Requests per (kind, segment)

# Auto-generate comparison pairs: all vs first experiment (baseline)
comparison_pairs: []

statistical_settings:
  confidence_level: 0.95
  bootstrap_samples: 1000
  paired_comparison: true

output_dir: "experiments/agent_eval/campaigns/campaign_001"

metadata:
  author: "evaluation team"
  created: "2026-11-03"
  purpose: "Parameter grid search"
```

### Option 2: Explicit Experiments

Manually specify each experiment:

```yaml
campaign_id: "campaign_002_explicit"
description: "Explicit experiment list"

dataset:
  tag: "default"
  split: "validation"

experiments:
  - name: "baseline_template"
    description: "Baseline with template inference"
    agent_config:
      agents: ["baseline", "type1"]
      inference_mode: "template"
      reflect_rounds: 0
    evaluation_config:
      per_segment: 20
    repetition_count: 1
    random_seed: 42
    tags: ["baseline"]

  - name: "planner_llm_reflect2"
    description: "Planner with LLM inference and 2 reflection rounds"
    agent_config:
      agents: ["planner"]
      inference_mode: "llm"
      reflect_rounds: 2
    evaluation_config:
      per_segment: 20
    repetition_count: 1
    random_seed: 42
    tags: ["planner"]

comparison_pairs:
  - ["baseline_template", "planner_llm_reflect2"]

statistical_settings:
  confidence_level: 0.95
  bootstrap_samples: 1000
  paired_comparison: true

output_dir: "experiments/agent_eval/campaigns/campaign_002"

metadata:
  author: "evaluation team"
  created: "2026-11-03"
  purpose: "Explicit experiment comparison"
```

## Supported Parameters

### Agent Config Parameters
- **agents**: List of agent names to run (e.g., `["baseline", "type1"]`, `["planner"]`, `["planner_memory"]`)
- **inference_mode**: `"template"` (deterministic, no LLM) or `"llm"` (LLM generates answer)
- **reflect_rounds**: Number of plan-reflect cycles (0 = disabled, 1+ = enabled)

### Evaluation Config Parameters
- **per_segment**: Number of requests per (kind, segment) combination

### Dataset Parameters
- **tag**: Data resource tag (must match data pipeline output)
- **split**: `"validation"` or `"test"`
- **filters**: Domain filters (e.g., `domains: ["Video_Games"]`)

Unknown keys in `agent_config`/`evaluation_config` are rejected — the runner raises
instead of silently dropping them. `random_seed` is applied via the config overlay
(`eval/baselines.baselines.seed`).

### Campaign-Level Runtime Defaults
- **default_agents**: Agent list used when `agent_config.agents` is absent
- **allow_missing_corpus_sources**: Passed to every experiment overlay
- **experiment_timeout_seconds**: Per-run subprocess timeout (default 3600)

Each experiment writes `config_overlay.yaml` into its run directory; the runner sets
`CONFIG_OVERLAY_PATH` for the `run_agent_eval.py` subprocess, and the overlay's
path/sha256/content is recorded in the experiment provenance.

## Parameter Grid Expansion

When using `parameter_grid`, the framework automatically:

1. **Generates all combinations** using Cartesian product
2. **Maps parameters** to the correct config location:
   - `agents`, `inference_mode`, `reflect_rounds` → `agent_config`
   - `per_segment` → `evaluation_config`
3. **Names experiments** based on parameter values:
   - Example: `exp_1_agents_[baseline, type1]_inference_mode_template_reflect_rounds_0`
4. **Auto-generates comparison pairs** (if empty):
   - Compares all experiments against the first one (baseline)

## Experiment Naming Convention

Auto-generated experiment names follow this pattern:
```
exp_{index}_{param1}_{value1}_{param2}_{value2}_...
```

For example:
- `exp_1_agents_[baseline, type1]_inference_mode_template_reflect_rounds_0`
- `exp_2_agents_[planner]_inference_mode_template_reflect_rounds_0`
- `exp_3_agents_[planner_memory]_inference_mode_llm_reflect_rounds_2`

## Output Structure

```
experiments/agent_eval/campaigns/campaign_001/
├── campaign_result.json  # Complete campaign results with comparisons
├── baseline/
│   └── run_1/
│       └── exp_NNN/  # Actual experiment output from run_agent_eval.py
│           ├── config.json
│           ├── metrics.json
│           ├── trajectories.jsonl
│           ├── requests.jsonl
│           └── scored.jsonl
├── planner/
│   └── run_1/
│       └── exp_NNN/
└── planner_memory/
    └── run_1/
        └── exp_NNN/
```

## Campaign Result Format

`campaign_result.json` contains:

```json
{
  "campaign_id": "campaign_001",
  "campaign_hash": "abc123...",
  "runs": [
    {
      "experiment_name": "baseline",
      "run_number": 1,
      "output_dir": "path/to/exp",
      "success": true,
      "duration_seconds": 123.45,
      "metrics": {
        "baseline_similar_task_success": 0.85,
        "baseline_similar_precision@10": 0.90,
        ...
      }
    },
    ...
  ],
  "comparisons": {
    "baseline_vs_planner": {
      "status": "success",
      "experiment_a": "baseline",
      "experiment_b": "planner",
      "deltas": {
        "baseline_similar_task_success": {
          "a": 0.85,
          "b": 0.92,
          "delta": 0.07,
          "relative_delta": 0.082
        },
        ...
      }
    },
    ...
  },
  "summary": {
    "total_runs": 3,
    "successful_runs": 3,
    "failed_runs": 0,
    "success_rate": 1.0,
    "average_duration_seconds": 150.0,
    "experiment_stats": {
      "baseline": {"total": 1, "success": 1, "failed": 0},
      ...
    }
  },
  "timestamp": "2026-11-03T12:00:00Z",
  "git_sha": "abc123..."
}
```

## Prerequisites

Before running a campaign, ensure:

1. **Data pipeline has been run** for the specified tag:
   ```bash
   python scripts/data_pipeline/run_pipeline.py --stages all --tag <your_tag>
   ```

2. **Corpus and splits exist** in `resource/`:
   - `resource/mapped/` (ID mappings)
   - `resource/splits/` (train/validation/test splits)
   - `resource/corpus/` (SQLite corpus)

3. **LLM provider is configured** (if using planner agents):
   - Set `LLM_API_KEY` and `LLM_BASE_URL` environment variables
   - Or configure in `configs/agent/llm.yaml`

4. **Optional: corpus behavior** — `use_prebuilt_corpus` /
   `allow_missing_corpus_sources` are set in `configs/agent/agent_eval.yaml`
   (or per-experiment via the generated `config_overlay.yaml`):
   ```yaml
   agent/agent_eval:
     agent_eval:
       use_prebuilt_corpus: false
       allow_missing_corpus_sources: true
   ```

## Integration with run_agent_eval.py

The campaign runner internally calls `run_agent_eval.py` for each experiment:

- Each experiment = one call to `run_agent_eval.py` with only operational
  selectors (`--tag`, `--eval-on`, `--domain`). Hyperparameters
  (`agents`, `per_segment`, `inference.mode`, `reflect_rounds`,
  `trajectory_file`, corpus flags) are written to a per-experiment
  `config_overlay.yaml` under the experiment directory and applied through
  the `CONFIG_OVERLAY_PATH` environment variable.
- Repetition count = number of times to repeat the same configuration
- Results are automatically aggregated and compared

## Comparison Statistics

Currently, the framework provides simple delta comparisons:
- Absolute delta: `metric_b - metric_a`
- Relative delta: `(metric_b - metric_a) / metric_a`

Future enhancements could include:
- Bootstrap confidence intervals
- Statistical significance tests (t-test, Wilcoxon)
- Effect size calculations (Cohen's d)

## Troubleshooting

### "Script failed with return code X"

Check the stdout/stderr in the campaign result or run the experiment manually:
```bash
python scripts/evaluation/run_agent_eval.py --tag <tag>
```

### "Metrics file not found"

The experiment may have failed before saving results. Check the experiment directory for errors.

### "Data pipeline not run"

Run the data pipeline first:
```bash
python scripts/data_pipeline/run_pipeline.py --stages all --tag <tag>
```

## Example Workflows

### Ablation Study: Planner vs No Planner

```yaml
experiments:
  - name: "no_planner"
    agent_config:
      agents: ["baseline", "type1"]
  - name: "with_planner"
    agent_config:
      agents: ["planner"]

comparison_pairs:
  - ["no_planner", "with_planner"]
```

### Memory Ablation

```yaml
experiments:
  - name: "planner_no_memory"
    agent_config:
      agents: ["planner"]
  - name: "planner_with_memory"
    agent_config:
      agents: ["planner_memory"]

comparison_pairs:
  - ["planner_no_memory", "planner_with_memory"]
```

### Reflection Rounds

```yaml
experiments:
  - name: "no_reflection"
    agent_config:
      agents: ["planner"]
      reflect_rounds: 0
  - name: "with_reflection"
    agent_config:
      agents: ["planner"]
      reflect_rounds: 2

comparison_pairs:
  - ["no_reflection", "with_reflection"]
```
