# Experiments Organization

This directory contains all experiment results, logs, and test outputs organized by category for better navigation and maintainability.

## Directory Structure

### 📁 `baselines/`
Baseline model experiment results and tuning outputs.

**Contents:**
- `exp_001/`, `exp_002/`, `exp_003/` - Individual baseline experiment runs
- `phase4_baselines/` - Phase 4 baseline evaluation results
- `smoke_baselines/` - Smoke test results for baseline models

**Each experiment directory contains:**
- `config.yaml` - Configuration used for the experiment
- `metrics.json` - Evaluation metrics
- `README.md` - Experiment description and results summary

**Related scripts:**
- `scripts/evaluation/run_baselines.py`
- `scripts/evaluation/tune_baselines.py`

---

### 📁 `agent_eval/`
Agent evaluation experiment results comparing different agent configurations.

**Contents:**
- `exp_002/`, `exp_003/` - Individual agent evaluation runs

**Each experiment directory contains:**
- `config.yaml` - Agent evaluation configuration
- `metrics.json` - Agent performance metrics
- `requests.jsonl` - Test requests used
- `scored.jsonl` - Scored trajectories
- `README.md` - Experiment summary

**Related scripts:**
- `scripts/evaluation/run_agent_eval.py`
- `scripts/experiments/compare_experiments.py`

---

### 📁 `logs/`
All pipeline and tool execution logs (consolidated from various stages).

**Contents:**
- `eda_video_games.log` - EDA statistics for Video_Games domain
- `phase3_toys_and_games.log` - Phase 3 processing log for Toys_and_Games
- `phase3_video_games.log` - Phase 3 processing log for Video_Games
- `pipeline_video_games.log` - Full pipeline execution log
- `run_tool.log` - Tool validation and execution log
- `stage1_electronics.log` - Stage 1 cleaning log for Electronics
- `stage1_toys_and_games.log` - Stage 1 cleaning log for Toys_and_Games
- `stage1_video_games.log` - Stage 1 cleaning log for Video_Games

**Log sources:**
- Data pipeline stages (stage1, stage2, stage3)
- Tool validation (`run_tools.py`)
- EDA scripts (`run_eda.py`)
- Other pipeline-related operations

**Configuration:**
- Log directory is configured in `configs/path/data_paths.yaml` → `paths.log_dir`
- Currently set to: `experiments/logs`

---

### 📁 `test_logs/`
Test execution logs and results reports.

**Contents:**
- `test_results_YYYYMMDD_HHMMSS.md` - Individual test run reports

**Log sources:**
- Pytest test runs
- Test result generation scripts
- Integration test outputs

**Note:** Test logs are automatically generated during test execution and are not tracked in version control (see `.gitignore`).

---

### 📁 `data_pipeline/`
Data pipeline experiment results (reserved for future use).

**Intended contents:**
- Pipeline optimization experiments
- Data quality analysis results
- Pipeline benchmarking outputs

**Related scripts:**
- `scripts/data_pipeline/stage1_clean_domain.py`
- `scripts/data_pipeline/stage2_merge_filter.py`
- `scripts/data_pipeline/stage3_map_split.py`

---

### 📁 `smoke_tests/`
Smoke test results for quick integration validation (reserved for future use).

**Intended contents:**
- LLM agent smoke test results
- Tool integration smoke tests
- Quick validation experiment outputs

**Related scripts:**
- `scripts/llm_agent/smoke_real_llm.py`

---

## Configuration

### Path Configuration

All experiment-related paths are configured in `configs/path/data_paths.yaml`:

```yaml
paths:
  log_dir: "experiments/logs"           # Pipeline/tool logs
  experiments_dir: "experiments"         # Experiment artifacts
```

### Git Ignore

The following are excluded from version control (see `.gitignore`):
- `experiments/logs/` - All pipeline and tool logs
- `experiments/test_logs/` - All test execution logs
- `experiments/**/trajectories.jsonl` - Agent trajectory files

Experiment results (config.yaml, metrics.json, README.md) are tracked by default.

---

## Quick Reference

| What you need | Location | Related Script |
|---------------|----------|----------------|
| Baseline results | `experiments/baselines/` | `scripts/evaluation/run_baselines.py` |
| Agent evaluation results | `experiments/agent_eval/` | `scripts/evaluation/run_agent_eval.py` |
| Pipeline execution logs | `experiments/logs/` | Various pipeline scripts |
| Test results | `experiments/test_logs/` | `pytest` |
| Compare experiments | `experiments/` (root) | `scripts/experiments/compare_experiments.py` |

---

## Running Experiments

### Baseline Evaluation
```bash
PYTHONPATH=. python scripts/evaluation/run_baselines.py --eval-on validation
# Results appear in experiments/baselines/exp_NNN/
```

### Agent Evaluation
```bash
PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --per-segment 2
# Results appear in experiments/agent_eval/exp_NNN/
```

### Pipeline with Logging
```bash
PYTHONPATH=. python scripts/data_pipeline/stage1_clean_domain.py --domain Video_Games
# Logs appear in experiments/logs/stage1_video_games.log
```

### Tool Validation
```bash
PYTHONPATH=. python scripts/tools/run_tools.py
# Logs appear in experiments/logs/run_tool.log
```

---

## Log Naming Convention

Logs follow these naming patterns:
- `<stage>_<domain>.log` - Stage-specific logs (e.g., `stage1_video_games.log`)
- `<phase>_<domain>.log` - Phase-specific logs (e.g., `phase3_video_games.log`)
- `<script_name>.log` - Script-specific logs (e.g., `run_tool.log`, `eda_video_games.log`)
- `test_results_YYYYMMDD_HHMMSS.md` - Test result reports

---

## Experiment Directory Convention

Each experiment follows this structure:
```
exp_NNN/
├── config.yaml       # Configuration snapshot
├── metrics.json      # Evaluation metrics
├── README.md         # Human-readable summary
├── requests.jsonl    # (agent eval) Test requests
├── scored.jsonl      # (agent eval) Scored trajectories
└── trajectories.jsonl # (agent eval) Raw trajectories (not tracked)
```

---

## Notes

- All logs are now consolidated under `experiments/` for unified organization
- Pipeline data (raw, cleaned, filtered, mapped, splits) remains in `resource/`
- Test logs are separate from pipeline logs for clarity
- Experiment numbering is global across all experiment types
- Log paths are configurable via `data_paths.yaml` for flexibility
