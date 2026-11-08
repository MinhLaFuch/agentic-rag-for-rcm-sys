# Phase 3 Move Plan: Merge package/tools/evaluation into package/evaluation

## Detailed File Categorization

### Current Structure

**package/tools/evaluation/** (20 root files + metrics/ subdirectory with 8 files):

**Core Evaluation Logic:**
- `evaluate_recommender.py` - Main recommender evaluation (sparse matrix, ranking metrics)
- `evaluate_ranking.py` - Alternative ranking metrics (pandas-based, for baselines)
- `evaluation_protocol.py` - Protocol validation (temporal, metadata, cohort policies)

**Metrics (ranking/retrieval):**
- `metrics/` directory (8 files):
  - `average_precision_at_k.py`
  - `hit_rate_at_k.py`
  - `mrr_at_k.py`
  - `ndcg_at_k.py`
  - `precision_at_k.py`
  - `ranking_metrics_at_k.py` (wrapper that imports all others)
  - `recall_at_k.py`
- `candidate_retrieval_metrics.py` - Retrieval quality metrics (recall, hit_rate, coverage)
- `item_familiarity_metrics.py` - Familiarity-based metrics (warm vs cold items)

**Data Structures:**
- `_dataclass.py` - EvaluationResult dataclass
- `_helper.py` - Helper functions (assign_segments, _git_commit)

**Experiment Management:**
- `save_experiment.py` - Save experiment results (config.yaml, metrics.json, README.md)
- `next_experiment_dir.py` - Generate next exp_XXX directory name
- `ranking_run_store.py` - SQLite checkpoint storage for streaming evaluation
- `ranking_stream_summary.py` - Streaming evaluation summary (merges, variants, latency)

**Configuration:**
- `parameter_grid.py` - Hyperparameter grid expansion (itertools.product)
- `merge_model_params.py` - Merge baseline config with model params
- `select_fit_target.py` - Fit/target selection protocol (validation vs test)
- `segment_users_by_history.py` - User segmentation (cold/sparse/warm)

**Utilities:**
- `latency_summary.py` - Latency metrics (mean, p50, p95)
- `hardware_info.py` - Hardware info collection
- `sha256_file.py` - File hashing utility
- `normalize_query_text.py` - Text normalization
- `stage_progress.py` - Stage progress tracking

**package/evaluation/** (agent evaluation):
- Root files: evaluate_product_reply.py, evaluate_product_reply_with_jev.py, score_trajectory.py, summarize.py, build_run_provenance.py, _schema.py
- Subdirectories: ablation/, campaign/, component/, diagnostics/, judge/, layer1_outcome/, layer2_interaction/, layer3_grounding/, layer4_process/, layer5_deployment/, multi_turn/, reporting/, requests/, statistics/

## Proposed Detailed Organization

```
package/evaluation/
├── recommender/                          # NEW: model/recommender evaluation
│   ├── __init__.py                       # exports from subdirectories
│   │
│   ├── core/                             # Core evaluation logic
│   │   ├── __init__.py
│   │   ├── evaluate_recommender.py       # Main sparse matrix evaluation
│   │   ├── evaluate_ranking.py           # Pandas-based baseline evaluation
│   │   ├── evaluation_protocol.py        # Protocol validation
│   │   ├── _dataclass.py                # EvaluationResult dataclass
│   │   └── _helper.py                  # Helper functions
│   │
│   ├── metrics/                          # Ranking/retrieval metrics
│   │   ├── __init__.py
│   │   ├── ranking/                      # Standard ranking metrics
│   │   │   ├── __init__.py
│   │   │   ├── average_precision_at_k.py
│   │   │   ├── hit_rate_at_k.py
│   │   │   ├── mrr_at_k.py
│   │   │   ├── ndcg_at_k.py
│   │   │   ├── precision_at_k.py
│   │   │   ├── ranking_metrics_at_k.py   # Wrapper importing all
│   │   │   └── recall_at_k.py
│   │   └── retrieval/                    # Retrieval-specific metrics
│   │       ├── __init__.py
│   │       ├── candidate_retrieval_metrics.py
│   │       └── item_familiarity_metrics.py
│   │
│   ├── experiment/                       # Experiment management
│   │   ├── __init__.py
│   │   ├── save_experiment.py            # Save results (config/metrics/README)
│   │   ├── next_experiment_dir.py        # Generate exp_XXX directory
│   │   ├── ranking_run_store.py          # SQLite checkpoint storage
│   │   └── ranking_stream_summary.py     # Streaming evaluation summary
│   │
│   ├── config/                           # Configuration helpers
│   │   ├── __init__.py
│   │   ├── parameter_grid.py             # Hyperparameter grid expansion
│   │   ├── merge_model_params.py         # Merge model configs
│   │   ├── select_fit_target.py          # Fit/target selection
│   │   └── segment_users_by_history.py  # User segmentation
│   │
│   └── utils/                            # General utilities
│       ├── __init__.py
│       ├── latency_summary.py            # Latency metrics
│       ├── hardware_info.py              # Hardware info
│       ├── sha256_file.py               # File hashing
│       ├── normalize_query_text.py      # Text normalization
│       └── stage_progress.py             # Stage progress
│
├── agent/                                # NEW: agent evaluation (existing reorganized)
│   ├── __init__.py
│   ├── component/                        # Component benchmarks
│   ├── multi_turn/                       # Multi-turn evaluation
│   ├── layer1_outcome/                   # Outcome scoring
│   ├── layer2_interaction/
│   ├── layer3_grounding/
│   ├── layer4_process/
│   └── layer5_deployment/
│
├── ablation/                             # Existing
├── campaign/                             # Existing
├── diagnostics/                          # Existing
├── judge/                                # Existing
├── reporting/                            # Existing
├── requests/                             # Existing
├── statistics/                           # Existing
│
├── product_reply/                         # NEW: product reply evaluation
│   ├── __init__.py
│   ├── evaluate_product_reply.py         # Rule-based evaluation
│   └── evaluate_product_reply_with_jev.py # Jev-based evaluation
│
├── trajectory/                            # NEW: trajectory scoring & aggregation
│   ├── __init__.py
│   ├── score_trajectory.py               # Orchestrate layer1-5 scoring
│   └── summarize.py                      # Aggregate scored rows (mean/percentiles)
│
├── provenance/                            # NEW: run metadata & provenance
│   ├── __init__.py
│   └── build_run_provenance.py          # Hash prompts, schemas, git state, limits
│
├── _schema.py                            # Existing (root level - shared schemas)
│
└── ARCHITECTURE.md, CAMPAIGN.md, etc.    # Existing docs
```

## Detailed Move Operations

### Step 1: Create directory structure
```bash
mkdir -p package/evaluation/recommender/core
mkdir -p package/evaluation/recommender/metrics/ranking
mkdir -p package/evaluation/recommender/metrics/retrieval
mkdir -p package/evaluation/recommender/experiment
mkdir -p package/evaluation/recommender/config
mkdir -p package/evaluation/recommender/utils
mkdir -p package/evaluation/agent
```

### Step 2: Move files to recommender/core/
```bash
git mv package/tools/evaluation/evaluate_recommender.py package/evaluation/recommender/core/
git mv package/tools/evaluation/evaluate_ranking.py package/evaluation/recommender/core/
git mv package/tools/evaluation/evaluation_protocol.py package/evaluation/recommender/core/
git mv package/tools/evaluation/_dataclass.py package/evaluation/recommender/core/
git mv package/tools/evaluation/_helper.py package/evaluation/recommender/core/
```

### Step 3: Move files to recommender/metrics/ranking/
```bash
git mv package/tools/evaluation/metrics/average_precision_at_k.py package/evaluation/recommender/metrics/ranking/
git mv package/tools/evaluation/metrics/hit_rate_at_k.py package/evaluation/recommender/metrics/ranking/
git mv package/tools/evaluation/metrics/mrr_at_k.py package/evaluation/recommender/metrics/ranking/
git mv package/tools/evaluation/metrics/ndcg_at_k.py package/evaluation/recommender/metrics/ranking/
git mv package/tools/evaluation/metrics/precision_at_k.py package/evaluation/recommender/metrics/ranking/
git mv package/tools/evaluation/metrics/ranking_metrics_at_k.py package/evaluation/recommender/metrics/ranking/
git mv package/tools/evaluation/metrics/recall_at_k.py package/evaluation/recommender/metrics/ranking/
```

### Step 4: Move files to recommender/metrics/retrieval/
```bash
git mv package/tools/evaluation/candidate_retrieval_metrics.py package/evaluation/recommender/metrics/retrieval/
git mv package/tools/evaluation/item_familiarity_metrics.py package/evaluation/recommender/metrics/retrieval/
```

### Step 5: Move files to recommender/experiment/
```bash
git mv package/tools/evaluation/save_experiment.py package/evaluation/recommender/experiment/
git mv package/tools/evaluation/next_experiment_dir.py package/evaluation/recommender/experiment/
git mv package/tools/evaluation/ranking_run_store.py package/evaluation/recommender/experiment/
git mv package/tools/evaluation/ranking_stream_summary.py package/evaluation/recommender/experiment/
```

### Step 6: Move files to recommender/config/
```bash
git mv package/tools/evaluation/parameter_grid.py package/evaluation/recommender/config/
git mv package/tools/evaluation/merge_model_params.py package/evaluation/recommender/config/
git mv package/tools/evaluation/select_fit_target.py package/evaluation/recommender/config/
git mv package/tools/evaluation/segment_users_by_history.py package/evaluation/recommender/config/
```

### Step 7: Move files to recommender/utils/
```bash
git mv package/tools/evaluation/latency_summary.py package/evaluation/recommender/utils/
git mv package/tools/evaluation/hardware_info.py package/evaluation/recommender/utils/
git mv package/tools/evaluation/sha256_file.py package/evaluation/recommender/utils/
git mv package/tools/evaluation/normalize_query_text.py package/evaluation/recommender/utils/
git mv package/tools/evaluation/stage_progress.py package/evaluation/recommender/utils/
```

### Step 8: Move root-level files to organized subdirectories
```bash
# Product reply evaluation
mkdir -p package/evaluation/product_reply
git mv package/evaluation/evaluate_product_reply.py package/evaluation/product_reply/
git mv package/evaluation/evaluate_product_reply_with_jev.py package/evaluation/product_reply/

# Trajectory scoring & aggregation
mkdir -p package/evaluation/trajectory
git mv package/evaluation/score_trajectory.py package/evaluation/trajectory/
git mv package/evaluation/summarize.py package/evaluation/trajectory/

# Provenance
mkdir -p package/evaluation/provenance
git mv package/evaluation/build_run_provenance.py package/evaluation/provenance/
```

### Step 9: Move existing agent evaluation to agent/ (optional, can defer)
```bash
git mv package/evaluation/component/ package/evaluation/agent/
git mv package/evaluation/multi_turn/ package/evaluation/agent/
git mv package/evaluation/layer1_outcome/ package/evaluation/agent/
git mv package/evaluation/layer2_interaction/ package/evaluation/agent/
git mv package/evaluation/layer3_grounding package/evaluation/agent/
git mv package/evaluation/layer4_process/ package/evaluation/agent/
git mv package/evaluation/layer5_deployment/ package/evaluation/agent/
```

### Step 10: Delete empty directories
```bash
rmdir package/tools/evaluation/metrics
rmdir package/tools/evaluation
```

### Step 11: Create __init__.py files
Create __init__.py in each new subdirectory to export appropriate symbols.

### Step 12: Update imports for root-level files
Add import mappings for the newly organized root-level files:

| Old Import | New Import |
|------------|------------|
| `from package.evaluation.evaluate_product_reply import` | `from package.evaluation.product_reply.evaluate_product_reply import` |
| `from package.evaluation.evaluate_product_reply_with_jev import` | `from package.evaluation.product_reply.evaluate_product_reply_with_jev import` |
| `from package.evaluation.score_trajectory import` | `from package.trajectory.score_trajectory import` |
| `from package.evaluation.summarize import` | `from package.trajectory.summarize import` |
| `from package.evaluation.build_run_provenance import` | `from package.evaluation.provenance.build_run_provenance import` |

### Step 11: Update imports (20 files)
Update all importers to use new paths:
- `from package.tools.evaluation.X` → `from package.evaluation.recommender.core.X` (or appropriate subdirectory)
- Update internal imports within moved files to adjust relative paths

## Import Mapping Table

| Old Import | New Import |
|------------|------------|
| `from package.tools.evaluation.evaluate_recommender import` | `from package.evaluation.recommender.core.evaluate_recommender import` |
| `from package.tools.evaluation.evaluate_ranking import` | `from package.evaluation.recommender.core.evaluate_ranking import` |
| `from package.tools.evaluation.evaluation_protocol import` | `from package.evaluation.recommender.core.evaluation_protocol import` |
| `from package.tools.evaluation.metrics.ranking_metrics_at_k import` | `from package.evaluation.recommender.metrics.ranking.ranking_metrics_at_k import` |
| `from package.tools.evaluation.candidate_retrieval_metrics import` | `from package.evaluation.recommender.metrics.retrieval.candidate_retrieval_metrics import` |
| `from package.tools.evaluation.item_familiarity_metrics import` | `from package.evaluation.recommender.metrics.retrieval.item_familiarity_metrics import` |
| `from package.tools.evaluation.save_experiment import` | `from package.evaluation.recommender.experiment.save_experiment import` |
| `from package.tools.evaluation.ranking_run_store import` | `from package.evaluation.recommender.experiment.ranking_run_store import` |
| `from package.tools.evaluation.ranking_stream_summary import` | `from package.evaluation.recommender.experiment.ranking_stream_summary import` |
| `from package.tools.evaluation.parameter_grid import` | `from package.evaluation.recommender.config.parameter_grid import` |
| `from package.tools.evaluation.merge_model_params import` | `from package.evaluation.recommender.config.merge_model_params import` |
| `from package.tools.evaluation.select_fit_target import` | `from package.evaluation.recommender.config.select_fit_target import` |
| `from package.tools.evaluation.segment_users_by_history import` | `from package.evaluation.recommender.config.segment_users_by_history import` |
| `from package.tools.evaluation.latency_summary import` | `from package.evaluation.recommender.utils.latency_summary import` |
| `from package.tools.evaluation import EvaluationResult` | `from package.evaluation.recommender.core import EvaluationResult` |

## Risk Assessment

- **Risk:** Medium-High (20 importers, complex reorganization, internal import updates)
- **Test impact:** Will break tests until all imports updated
- **Rollback:** `git revert`

## Recommendation

This detailed organization provides:
1. **Clear separation**: core evaluation vs metrics vs experiment vs config vs utils
2. **Logical grouping**: Related functionality grouped together
3. **Scalability**: Easy to add new metrics to appropriate subdirectory
4. **Atomic moves**: Each file has a clear destination
