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
    --review-path /path/to/review_Video_Games.jsonl.gz \
    --output-dir /path/to/output \
    --chunk-size 100000

# Stage 2 options
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages 2 --cold-start-report

# Stage 4 options
PYTHONPATH=. python scripts/data_pipeline/run_pipeline.py --stages 4 \
    --eval-on validation \
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
PYTHONPATH=. python scripts/demo/run_demo.py --tag v1 --domain Video_Games --eval-on validation

# Live mode options
PYTHONPATH=. python scripts/demo/run_demo.py \
    --tag v1 \
    --domain Video_Games \
    --eval-on validation \
    --no-prebuilt \
    --allow-missing-corpus-sources \
    --host 0.0.0.0 \
    --port 7860 \
    --inference-mode llm  # or template
```

**Arguments**:
| Arg | Default | Description |
|-----|---------|-------------|
| `--mock` | false | Mock mode (no data/LLM) |
| `--tag` | from run_tag.yaml | Data tag |
| `--eval-on` | validation | validation/test split |
| `--domain` | all | Domain filter (repeatable) |
| `--no-prebuilt` | false | Build corpus/ItemKNN in RAM |
| `--allow-missing-corpus-sources` | false | Allow missing metadata sources |
| `--host` | 127.0.0.1 | Server host |
| `--port` | 7860 | Server port |
| `--inference-mode` | llm | llm / template |

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

# Model selection
PYTHONPATH=. python scripts/tools/run_tools.py --model knn  # or bpr

# Evaluation options
PYTHONPATH=. python scripts/tools/run_tools.py --eval-users 100 --negatives 100 --top-k 10
```

**Arguments**:
| Arg | Default | Description |
|-----|---------|-------------|
| `--tag` | from run_tag.yaml | Data tag |
| `--domain` | all | Domain filter (repeatable) |
| `--model` | knn | knn / bpr |
| `--eval-users` | 100 | Sample users for evaluation |
| `--negatives` | 100 | Negatives per user for ranking eval |
| `--top-k` | 10 | K for Hit Rate / NDCG |

---

## 5. Baseline Evaluation (Phase 4)

### `scripts/evaluation/run_baselines.py`
Run baseline models (popularity, ItemKNN, BPR-MF).

```bash
# Default
PYTHONPATH=. python scripts/evaluation/run_baselines.py --eval-on validation

# Custom tag + models
PYTHONPATH=. python scripts/evaluation/run_baselines.py --tag vg_toys --models popularity,item_knn

# Custom K values
PYTHONPATH=. python scripts/evaluation/run_baselines.py --ks 5,10,20

# Custom directories
PYTHONPATH=. python scripts/evaluation/run_baselines.py \
    --splits-dir /path/to/splits \
    --experiments-dir /path/to/experiments
```

**Arguments**:
| Arg | Default | Description |
|-----|---------|-------------|
| `--tag` | from run_tag.yaml | Data tag |
| `--splits-dir` | from data_paths.yaml | Splits directory |
| `--eval-on` | validation | validation / test |
| `--models` | from baselines.yaml | Comma-separated: popularity,item_knn,bpr_mf |
| `--ks` | from recommendation_metrics.yaml | K values (e.g., 5,10,20) |
| `--experiments-dir` | from data_paths.yaml | Output directory |

### `scripts/evaluation/tune_baselines.py`
Hyperparameter tuning on validation.

```bash
# Validation tuning only
PYTHONPATH=. python scripts/evaluation/tune_baselines.py

# With final test run (one-time)
PYTHONPATH=. python scripts/evaluation/tune_baselines.py --tag vg_toys --run-final-test

# Custom models + selection metric
PYTHONPATH=. python scripts/evaluation/tune_baselines.py --models item_knn,bpr_mf --selection-metric recall@10
```

**Arguments**:
| Arg | Default | Description |
|-----|---------|-------------|
| `--tag` | from run_tag.yaml | Data tag |
| `--splits-dir` | from data_paths.yaml | Splits directory |
| `--models` | from tuning.yaml | popularity,item_knn,bpr_mf |
| `--ks` | from recommendation_metrics.yaml | K values |
| `--selection-metric` | from tuning.yaml | e.g., recall@10 |
| `--run-final-test` | false | Refit on train+val, eval test |
| `--experiments-dir` | from data_paths.yaml | Output directory |

---

## 6. Candidate Recall & Retrieval Analysis

### `scripts/evaluation/candidate_recall.py`
Measure candidate source coverage (popularity, ItemCF, SemanticSearch).

```bash
# Default
PYTHONPATH=. python scripts/evaluation/candidate_recall.py --eval-on validation

# Oracle queries (target-informed, upper bound)
PYTHONPATH=. python scripts/evaluation/candidate_recall.py --eval-on validation --query-modes category_oracle

# Custom tag + domains
PYTHONPATH=. python scripts/evaluation/candidate_recall.py --tag vg_toys --domain Video_Games --domain Toys_and_Games

# Custom budgets / sample sizes
PYTHONPATH=. python scripts/evaluation/candidate_recall.py --per-segment 50 --seed-items 3 --query-items 5 --neighbors 10
```

**Arguments**:
| Arg | Default | Description |
|-----|---------|-------------|
| `--tag` | from run_tag.yaml | Data tag |
| `--domain` | all | Domain filter (repeatable) |
| `--eval-on` | validation | validation / test |
| `--splits-dir` | from data_paths.yaml | Splits directory |
| `--per-segment` | from candidate_recall.yaml | Users per segment |
| `--seed-items` | from candidate_recall.yaml | Items for ItemCF seed |
| `--query-items` | from candidate_recall.yaml | Items for semantic query |
| `--neighbors` | from candidate_recall.yaml | ItemCF neighbors |
| `--query-modes` | history | history / category_oracle |
| `--no-prebuilt-corpus` | false | Build corpus in RAM |
| `--allow-missing-corpus-sources` | false | Allow missing metadata |

---

## 7. Agent Evaluation (Phase 8+)

### `scripts/evaluation/run_agent_eval.py`
Full agent evaluation with LLM planner.

```bash
# Tiny trial (2 per segment, no LLM)
PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --per-segment 2 --inference-mode template

# Baseline + Type1 (no LLM)
PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --agents baseline,type1 --inference-mode template

# LLM planner, template answers
PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --inference-mode template

# Resume interrupted run
PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --resume

# Full run with LLM
PYTHONPATH=. python scripts/evaluation/run_agent_eval.py \
    --per-segment 50 \
    --agents baseline,type1,planner,planner_memory \
    --inference-mode llm \
    --llm-retries 1

# Oracle scope (constrained/cold_text only)
PYTHONPATH=. python scripts/evaluation/run_agent_eval.py --request-scope oracle
```

**Arguments**:
| Arg | Default | Description |
|-----|---------|-------------|
| `--tag` | from run_tag.yaml | Data tag |
| `--eval-on` | validation | validation / test |
| `--per-segment` | from agent_eval.yaml | Users per segment |
| `--agents` | all | baseline,type1,planner,planner_memory |
| `--request-scope` | realistic | realistic / oracle |
| `--inference-mode` | template | llm / template |
| `--llm-retries` | 1 | Max LLM retries for answer |
| `--seed` | 42 | Random seed |
| `--resume` | false | Resume from trajectory log |
| `--no-prebuilt` | false | Build corpus in RAM |
| `--allow-missing-corpus-sources` | false | Allow missing metadata |
| `--experiments-dir` | from data_paths.yaml | Output directory |

### `scripts/evaluation/ranking_eval.py`
Fixed-candidate deterministic ranking evaluation.

```bash
# Default
PYTHONPATH=. python scripts/evaluation/ranking_eval.py --eval-on validation

# Custom tag + domains
PYTHONPATH=. python scripts/evaluation/ranking_eval.py --tag vg_toys --domain Video_Games

# Resume from checkpoint
PYTHONPATH=. python scripts/evaluation/ranking_eval.py --resume

# Fast mode (no retrieval replay)
PYTHONPATH=. python scripts/evaluation/ranking_eval.py --no-retrieval-replay
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

# Custom config
PYTHONPATH=. python scripts/experiments/compare_experiments.py --config agent/ablation
```

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
    --selection-pilot path/to/selection_pilot \
    --output-root path/to/output \
    --seed 42 \
    --bootstrap-samples 5000
```

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
| Baseline experiments | `experiments/exp_NNN/` |
| Agent eval experiments | `experiments/agent_eval/exp_NNN/` |
| Candidate recall experiments | `experiments/candidate_recall/exp_NNN/` |
| Ranking eval experiments | `experiments/ranking_eval/exp_NNN/` |
| Ablation comparisons | `experiments/agent_eval/ablation/` |

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