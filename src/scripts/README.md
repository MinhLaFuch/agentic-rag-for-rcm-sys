# Scripts Organization

This directory contains all executable scripts organized by category for better navigation and maintainability.

## Directory Structure

### 📁 `data_pipeline/`
Data processing and preparation scripts for the full pipeline from raw data to train/validation/test splits.

- **`run_pipeline.py`** - Run the full data pipeline or selected stages (clean domains, merge & filter, map & split)

**Usage**: Run all stages or specific stages with `--stages` flag

---

### 📁 `evaluation/`
Model evaluation and benchmarking scripts for baselines, agents, and retrieval tools.

- **`run_agent_eval.py`** - Evaluate agent performance (baseline, type1, planner, planner_memory)
- **`run_baselines.py`** - Run baseline models (random, popularity, item_knn, bpr_mf)
- **`tune_baselines.py`** - Hyperparameter tuning for baseline models
- **`candidate_recall.py`** - Measure candidate recall for retrieval tools (popularity, item_cf, semantic)
- **`benchmark_categories_any.py`** - Benchmark SemanticSearchTool with categories_any + FTS

**Usage**: Evaluate models on validation/test splits after data pipeline is complete

---

### 📁 `demo/`
Demo and UI scripts for showcasing the recommendation system.

- **`run_demo.py`** - Launch Gradio demo UI (mock mode or real data mode)
- **`demo_full_agent.py`** - Demo with full PlanExecutor and all 5 tools

**Usage**: Run demo for presentation or testing with real LLM

---

### 📁 `eda_diagnostic/`
Exploratory Data Analysis and diagnostic scripts for understanding data quality and issues.

- **`run_eda.py`** - Compute interaction statistics on raw review data
- **`diagnose_splits.py`** - Diagnose split issues (e.g., why recall@10 ≡ 0)

**Usage**: Analyze data quality and debug pipeline issues

---

### 📁 `tools/`
Tool validation and testing scripts.

- **`run_tools.py`** - Run and validate all tools on real data (Stage 3 outputs + metadata)
- **`check_llm_provider.py`** - Health check for LLM provider configuration

**Usage**: Validate tool functionality and LLM connectivity

---

### 📁 `llm_agent/`
LLM agent testing and smoke test scripts.

- **`smoke_real_llm.py`** - Smoke test PlanExecutor with real LLM on synthetic fixtures

**Usage**: Quick integration test with real LLM before full evaluation

---

### 📁 `experiments/`
Experiment comparison and analysis scripts.

- **`compare_experiments.py`** - Compare ablation experiments and generate reports

**Usage**: Analyze and compare multiple experiment runs

---

## Quick Reference

| Task | Script Category | Script | Output Location |
|------|----------------|--------|-----------------|
| Process raw data | `data_pipeline/` | `run_pipeline.py` | `resource/` (data), `experiments/logs/` (logs) |
| Run baseline models | `evaluation/` | `run_baselines.py` | `experiments/baselines/` |
| Evaluate agents | `evaluation/` | `run_agent_eval.py` | `experiments/agent_eval/` |
| Launch demo UI | `demo/` | `run_demo.py` | N/A (interactive) |
| Analyze data quality | `eda_diagnostic/` | `run_eda.py`, `diagnose_splits.py` | `experiments/logs/` |
| Validate tools | `tools/` | `run_tools.py` | `experiments/logs/` |
| Test LLM integration | `llm_agent/` | `smoke_real_llm.py` | Console output |
| Compare experiments | `experiments/` | `compare_experiments.py` | Generated reports |

## Running Scripts

All scripts should be run from the project root with `PYTHONPATH=.python`:

```bash
# Example: Run demo
PYTHONPATH=. python scripts/demo/run_demo.py --mock

# Example: Run agent evaluation
PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --per-segment 2

# Example: Run data pipeline (all stages)
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages all

# Example: Run only stage 3 (map & split)
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages 3 --tag mytag
```

## Notes

- Tests are organized separately in the `tests/` directory with a similar categorization structure
- Configuration files for scripts are in `configs/` directory
- All script docstrings contain usage examples and detailed descriptions
- All logs (pipeline, tool, test) are now consolidated in `experiments/logs/` and `experiments/test_logs/`
- Experiment results are organized in `experiments/` by category (baselines, agent_eval, etc.)
