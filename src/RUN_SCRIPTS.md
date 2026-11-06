# Scripts & Tests Runner Reference

> **Working directory**: `src/` (always run with `PYTHONPATH=.`)
> **Config path convention**: `load_config("agent/tools")` reads `configs/agent/tools.yaml`

---

## 1. Data Pipeline (Phase 3)

### `scripts/data_pipeline/run_pipeline.py`
Run the full data pipeline or selected stages.

```bash
# Run all stages (1→2→3→4)
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py

# Run specific stages
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages 1
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages 1,2
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages 2,3,4

# Run for specific domains (default: all domains in domains.yaml)
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --domain Video_Games
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --domain Video_Games --domain Toys_and_Games

# Override run tag (default: tag from configs/path/run_tag.yaml)
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --tag my_run_v1

# Force overwrite existing outputs
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --force

# Stage 1 options
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages 1 --domain Video_Games \
    --review-path /path/to/review_Video_Games.jsonl.gz

# Stage 2 options
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages 2 --cold-start-report

# Stage 4 options
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages 4 \
    --skip-corpus \
    --skip-item-knn
```

**Stages**:
| Stage | Description |
|-------|-------------|
| 1 | Clean raw reviews per domain → `resource/cleaned/<domain>/interactions.parquet` |
| 2 | Merge domains + filter (k-core) → `resource/filtered/<tag>/interactions.parquet` |
| 3 | ID mapping + temporal split → `resource/mapped/<tag>/`, `resource/splits/<tag>/` |
| 4 | Build ItemCorpus SQLite + ItemKNN artifacts → `resource/corpus/<tag>/`, `resource/item_knn/<tag>/` |

---

## 2. EDA & Diagnostics

### `scripts/eda_diagnostic/run_eda.py`
Streaming EDA on raw review files.

```bash
# All domains
PYTHONPATH=. python scripts/eda_diagnostic/run_eda.py

# Specific domain(s)
PYTHONPATH=. python scripts/eda_diagnostic/run_eda.py --domain Video_Games
PYTHONPATH=. python scripts/eda_diagnostic/run_eda.py --domain Video_Games --domain Toys_and_Games

# Direct file path
PYTHONPATH=. python scripts/eda_diagnostic/run_eda.py --path /path/to/review_Video_Games.jsonl.gz
```

### `scripts/eda_diagnostic/diagnose_splits.py`
Check split quality (leakage, temporal order, user coverage).

```bash
PYTHONPATH=. python scripts/eda_diagnostic/diagnose_splits.py --tag v1 --domain Video_Games
```

---

## 3. Demo Scripts

### `scripts/demo/run_demo.py`
Gradio UI demo.

```bash
# Mock mode (no data/LLM needed)
PYTHONPATH=. python scripts/demo/run_demo.py --mock

# Live mode with real data
PYTHONPATH=. python scripts/demo/run_demo.py --tag v1 --domain Video_Games

# Live mode options (inference mode, corpus flags, eval split come from
# configs/agent/demo.yaml and configs/agent/inference.yaml — not CLI)
PYTHONPATH=. python scripts/demo/run_demo.py \
    --tag v1 \
    --domain Video_Games \
    --host 0.0.0.0 \
    --port 7860
```

**Arguments**:
| Arg | Default | Description |
|-----|---------|-------------|
| `--mock` | false | Mock mode (no data/LLM) |
| `--tag` | from run_tag.yaml | Data tag |
| `--domain` | all | Domain filter (repeatable) |
| `--host` | 127.0.0.1 | Server host |
| `--port` | 7860 | Server port |

Corpus behavior (`use_prebuilt_corpus`, `allow_missing_corpus_sources`,
`eval_on`) and inference mode are set in `configs/agent/demo.yaml` /
`configs/agent/inference.yaml`.

### `scripts/demo/demo_full_agent.py`
Reference wiring of all 5 tools for PlanExecutor (not runnable directly).

```bash
# Import in your script:
# from scripts.demo.demo_full_agent import build_tools, build_executor
```

---

## 4. Tool Validation

### `scripts/tools/check_llm_provider.py`
Health check LLM provider from config.

```bash
PYTHONPATH=. python scripts/tools/check_llm_provider.py
```

### `scripts/tools/run_tools.py`
Run all package/tools on real data (stage 3 outputs + metadata).

```bash
# Default tag + all domains
PYTHONPATH=. python scripts/tools/run_tools.py

# Custom tag + domains
PYTHONPATH=. python scripts/tools/run_tools.py --tag vg_toys --domain Video_Games
```

**Arguments**:
| Arg | Default | Description |
|-----|---------|-------------|
| `--tag` | from run_tag.yaml | Data tag |
| `--domain` | all | Domain filter (repeatable) |

Model, `eval_users`, `negatives`, `seed` are set in
`configs/eval/tool_validation.yaml`.

---

## 5. Baseline Evaluation (Phase 4)

### `scripts/evaluation/run_baselines.py`
Run baseline models (popularity, ItemKNN, BPR-MF).

```bash
# Default
PYTHONPATH=. python scripts/evaluation/run_baselines.py --eval-on validation
```

**Arguments**:
| Arg | Default | Description |
|-----|---------|-------------|
| `--tag` | from run_tag.yaml | Data tag |
| `--eval-on` | validation | validation / test |

Models (`baselines.yaml`), K values (`recommendation_metrics.yaml`), output
dir (`data_paths.outputs.baselines`) and all split paths (`data_paths.yaml`)
are configured in YAML — there are no CLI overrides.

### `scripts/evaluation/tune_baselines.py`
Hyperparameter tuning on validation.

```bash
# Validation tuning only
PYTHONPATH=. python scripts/evaluation/tune_baselines.py

# With tag
PYTHONPATH=. python scripts/evaluation/tune_baselines.py --tag vg_toys
```

**Arguments**:
| Arg | Default | Description |
|-----|---------|-------------|
| `--tag` | from run_tag.yaml | Data tag |

Model grids (`eval/tuning.yaml` `models`), `selection_metric`, K values, and
`run_final_test` are all configured in YAML — there are no CLI overrides.

---

## 6. Candidate Recall & Retrieval Analysis

### `scripts/evaluation/candidate_recall.py`
Measure candidate source coverage (popularity, ItemCF, SemanticSearch).

```bash
# Default
PYTHONPATH=. python scripts/evaluation/candidate_recall.py --eval-on validation

# Custom tag + domains
PYTHONPATH=. python scripts/evaluation/candidate_recall.py --tag vg_toys --domain Video_Games --domain Toys_and_Games
```

**Arguments**:
| Arg | Default | Description |
|-----|---------|-------------|
| `--tag` | from run_tag.yaml | Data tag |
| `--domain` | all | Domain filter (repeatable) |
| `--eval-on` | validation | validation / test |

Budgets, sample sizes, query modes, seeds, neighbors, metadata/query policy
and corpus behavior are all set in `configs/eval/candidate_recall.yaml` (and
`configs/eval/baselines.yaml`) — there are no CLI overrides.

---

## 7. Agent Evaluation (Phase 8+)

### `scripts/evaluation/run_agent_eval.py`
Full agent evaluation with LLM planner.

```bash
# Default
PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --eval-on validation

# Resume interrupted run
PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --resume
```

**Arguments**:
| Arg | Default | Description |
|-----|---------|-------------|
| `--tag` | from run_tag.yaml | Data tag |
| `--domain` | all | Domain filter (repeatable) |
| `--eval-on` | validation | validation / test |
| `--resume` | false | Resume from trajectory log |

Agents, per-segment counts, request scope, trajectory file, inference mode,
reflect rounds, metadata/query policy, corpus behavior and seeds are all set
in YAML (`configs/agent/agent_eval.yaml`, `agent/agent.yaml`,
`agent/inference.yaml`, `eval/candidate_recall.yaml`) — there are no CLI
overrides. For per-experiment variation use a config overlay
(`CONFIG_OVERLAY_PATH`, see `package/evaluation/campaign/`).

### `scripts/evaluation/ranking_eval.py`
Fixed-candidate deterministic ranking evaluation.

```bash
# Default
PYTHONPATH=. python scripts/evaluation/ranking_eval.py --eval-on validation

# Resume from checkpoint
PYTHONPATH=. python scripts/evaluation/ranking_eval.py --resume

# Freeze candidates from a compatible completed experiment
PYTHONPATH=. python scripts/evaluation/ranking_eval.py --candidates-from experiments/ranking_eval/exp_003
```

---

## 8. Product Reply Evaluation

### `scripts/evaluation/evaluate_with_jev.py`
Jev-based structured evaluation of assistant replies.

```bash
# From JSONL file
PYTHONPATH=. python scripts/evaluation/evaluate_with_jev.py --input-file data.jsonl

# Single evaluation
PYTHONPATH=. python scripts/evaluation/evaluate_with_jev.py \
    --request "I want a gaming laptop under $1000" \
    --items-file items.json \
    --answer "Here are 3 options..." \
    --config-file configs/eval/judge.yaml \
    --output-file result.json
```

**Input JSONL format**:
```jsonl
{"request": "user request", "items": [{"item_id": "...", "title": "...", ...}], "answer": "assistant reply"}
```

---

## 9. Ablation & Experiment Comparison

### `scripts/experiments/compare_experiments.py`
Compare ablation experiments per configs/agent/ablation.yaml.

```bash
PYTHONPATH=. python scripts/experiments/compare_experiments.py
```

Config is fixed to `configs/agent/ablation.yaml`; per-run variation goes through
`CONFIG_OVERLAY_PATH` (see §17).

---

## 10. LLM Smoke Test

### `scripts/llm_agent/smoke_real_llm.py`
Test PlanExecutor with real LLM on synthetic fixture.

```bash
PYTHONPATH=. python scripts/llm_agent/smoke_real_llm.py
```

---

## 11. Ranking Diagnostics

### `scripts/evaluation/analyze_ranking_bottlenecks.py`
Bottleneck analysis from saved candidate/score artifacts.

```bash
PYTHONPATH=. python scripts/evaluation/analyze_ranking_bottlenecks.py \
    --experiment path/to/exp_NNN \
    --selection-pilot path/to/selection_pilot
```

Seed and bootstrap sample count come from `configs/eval/ranking_diagnostics.yaml`; output goes to `data_paths.outputs.ranking_diagnostics`.

---

## 12. Tests (pytest)

### Running Tests

```bash
# All tests (from src/)
cd src
python -m pytest tests/ -q

# Specific test modules
python -m pytest tests/tools/score/ -q
python -m pytest tests/tools/retrieval/ -q
python -m pytest tests/tools/ranking/ -q
python -m pytest tests/config/ -q
python -m pytest tests/data/ -q
python -m pytest tests/agents/ -q
python -m pytest tests/evaluation/ -q

# With coverage
python -m pytest tests/ --cov=package --cov-report=term-missing

# Verbose
python -m pytest tests/tools/score/test_contract_baseline_scorer.py -v

# Exclude problematic test (pre-existing import issue)
python -m pytest tests/ -q --ignore=tests/tools/evaluation/test_protocol.py
```

### Test Structure
| Path | Description |
|------|-------------|
| `tests/config/` | Config loading, path hygiene |
| `tests/data/` | Pipeline stages, splits, leakage |
| `tests/tools/` | Tool contracts (score, retrieval, ranking, corpus, etc.) |
| `tests/agents/` | Agent planner, type1, inference |
| `tests/evaluation/` | Baselines, candidate recall, agent eval |
| `tests/demo/` | Demo components |

---

## 13. Common Environment Variables

```bash
# Required for LLM calls
export LLM_API_KEY="your-api-key"
export LLM_BASE_URL="https://api.openai.com/v1"  # or compatible endpoint

# Domain selection (used by config interpolation)
export DOMAIN=Video_Games

# Run from project root or src/ with PYTHONPATH=.
export PYTHONPATH=.
```

---

## 14. Quick Reference: Config Files

| Config | Path | Purpose |
|--------|------|---------|
| `agent/tools` | `configs/agent/tools.yaml` | Tool runtime limits |
| `agent/llm` | `configs/agent/llm.yaml` | LLM provider settings |
| `agent/agent` | `configs/agent/agent.yaml` | Agent limits (max steps, etc.) |
| `agent/agent_eval` | `configs/agent/agent_eval.yaml` | Agent eval settings |
| `eval/baselines` | `configs/eval/baselines.yaml` | Baseline model configs |
| `eval/tuning` | `configs/eval/tuning.yaml` | Hyperparameter grids |
| `eval/candidate_recall` | `configs/eval/candidate_recall.yaml` | Recall budgets |
| `eval/ranking_eval` | `configs/eval/ranking_eval.yaml` | Ranking eval settings |
| `eval/ranking_diagnostics` | `configs/eval/ranking_diagnostics.yaml` | Bottleneck analysis settings |
| `eval/tool_validation` | `configs/eval/tool_validation.yaml` | run_tools.py settings |
| `eval/memory_utility` | `configs/eval/memory_utility.yaml` | Memory utility analysis settings |
| `eval/categories_any_benchmark` | `configs/eval/categories_any_benchmark.yaml` | categories_any benchmark settings |
| `eval/component_benchmarks` | `configs/eval/component_benchmarks.yaml` | Component benchmark runs |
| `eval/recommendation_metrics` | `configs/eval/recommendation_metrics.yaml` | K values, metrics |
| `path/data_paths` | `configs/path/data_paths.yaml` | All filesystem paths |
| `path/run_tag` | `configs/path/run_tag.yaml` | Current run tag |
| `path/domains` | `configs/path/domains.yaml` | Domain list |

---

## 15. Output Locations

| Output | Location |
|--------|----------|
| Pipeline logs | `experiments/logs/<tag>/run_pipeline.log` |
| Tool validation log | `experiments/logs/<tag>/run_tools.log` |
| Baseline experiments | `experiments/baselines/exp_NNN/` |
| Agent eval experiments | `experiments/agent_eval/exp_NNN/` |
| Candidate recall experiments | `experiments/candidate_recall/exp_NNN/` |
| Ranking eval experiments | `experiments/ranking_eval/exp_NNN/` |
| Ranking diagnostics | `experiments/ranking_diagnostics/exp_NNN/` |
| Ablation comparisons | `experiments/agent_eval/ablation/` |
| Component benchmarks | `experiments/agent_eval/component_benchmarks/` |
| Memory utility analysis | `experiments/agent_eval/memory_utility_analysis/` |
| Multi-turn evaluation | `experiments/agent_eval/multi_turn/` |
| Test logs / results | `experiments/test_logs/` |

All of the above are configured in `outputs:` in `configs/path/data_paths.yaml` (relative to `experiments_dir`).

---

## 16. Common Patterns

```bash
# Always use PYTHONPATH=. from project root or cd src
cd /path/to/agentic-rag-for-rcm-sys
PYTHONPATH=. python src/scripts/...

# Or from src/
cd /path/to/agentic-rag-for-rcm-sys/src
python scripts/...

# Set domain for config interpolation
DOMAIN=Video_Games PYTHONPATH=. python scripts/...
```

## 17. Config Overlay (per-experiment overrides)

All tunables live in YAML; CLI flags are only operational selectors
(`--tag`, `--domain`, `--eval-on`, `--resume`, `--work-dir`,
`--candidates-from`, `--stages`, `--force`, `--mock`, `--host`, `--port`).

To run an experiment with different hyperparameters, write a YAML overlay
shaped like the config tree and point `CONFIG_OVERLAY_PATH` at it:

```yaml
# overlay.yaml
agent/agent_eval:
  agent_eval:
    agents: [baseline, type1]
    per_segment: 2
agent/inference:
  inference:
    mode: template
```

```bash
CONFIG_OVERLAY_PATH=/path/to/overlay.yaml PYTHONPATH=. \
    python scripts/evaluation/run_agent_eval.py --eval-on validation
```

The campaign runner (`package/evaluation/campaign/`) writes one overlay per
experiment automatically. Overlay fragments are deep-merged over the base
configs before Pydantic validation, and changing the overlay invalidates
cached limits.