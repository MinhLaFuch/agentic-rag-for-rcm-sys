# Agent Evaluation Framework Documentation

## Architecture Overview

The Agent Evaluation Framework is a comprehensive system for evaluating, comparing, and analyzing agent performance across multiple dimensions. It is organized into the following key packages:

### Package Structure

```
package/evaluation/
├── _schema.py                    # Core evaluation schemas
├── _loader.py                    # Dataset loading utilities
├── _evaluator.py                 # Base evaluator class
├── _regression.py                # Regression comparison utilities
├── build_run_provenance.py       # Provenance tracking
├── component/                    # Component-level evaluation
│   ├── _schema.py               # Component schemas
│   ├── _evaluator.py            # Component evaluator base
│   ├── _loader.py               # Component dataset loader
│   ├── _regression.py            # Component regression
│   ├── run.py                   # Component benchmark runner
│   ├── run_all.py               # Unified component runner
│   └── benchmarks/              # Component benchmark datasets
│       ├── planner_dataset.jsonl
│       ├── executor_dataset.jsonl
│       ├── grounding_dataset.jsonl
│       ├── integration_dataset.jsonl
│       └── memory_correctness_dataset.jsonl
├── multi_turn/                   # Multi-turn conversation evaluation
│   ├── _schema.py               # Conversation schemas
│   ├── evaluator.py             # Multi-turn evaluator
│   ├── run.py                   # Multi-turn CLI runner
│   ├── reporting.py             # Multi-turn reporting
│   └── conversations.jsonl      # Conversation scenarios
├── campaign/                     # Campaign orchestration
│   ├── _schema.py               # Campaign schemas
│   ├── runner.py                # Campaign execution runner
│   └── example_campaign.yaml    # Example campaign config
├── statistics/                   # Statistical analysis
│   ├── bootstrap.py             # Bootstrap CI and significance tests
│   └── __init__.py
└── reporting/                    # Report generation
    ├── generator.py             # Markdown/CSV report generators
    ├── visualizations.py        # Chart generation (placeholders)
    └── generate_example_report.py
```

### Core Concepts

#### Evaluation Layers (L1-L5)

1. **L1: Recommendation Quality**
   - Precision@K, Recall@K, Hit Rate@K, NDCG@K, MRR@K, MAP@K
   - Seen item rate, seed-in-result, distinct domains
   - Target reachability and category coverage

2. **L2: Task Success**
   - Task success, constraint satisfaction, price unknown rate
   - Clarification tracking, grounded-answer conditions
   - Preference alignment, negative preference violation
   - Exclusion compliance, appropriate clarification

3. **L3: Retrieval and Grounding**
   - Target availability, candidate generation, retrieval, filtering, ranking
   - Query hit analysis, retrieval funnel stages (S0-S5)
   - Answer grounding with evidence support

4. **L4: Planning and Execution**
   - Plan validity, planning attempts, truncation
   - Step count, step success rate, reflection count
   - Tool selection, argument validity, ranker usage

5. **L5: Efficiency and Cost**
   - Prompt tokens, completion tokens, LLM latency
   - Tool latency, wall time, inference tokens
   - Cost per request, cost breakdown by component

#### Request Kinds (Seven Labels)

1. **similar**: Similar items to seed items
2. **personalized**: Personalized recommendations using memory
3. **constrained**: Constrained by filters (price, category, etc.)
4. **cold_text**: Cold-start with text only
5. **ambiguous**: Ambiguous requests requiring clarification
6. **exclusion**: Exclude specific items or categories
7. **unanswerable**: Requests that cannot be answered from available information

#### Component Evaluation

- **Planner**: Tool selection, argument correctness, plan validity
- **Executor**: Execution success, retries, reflection behavior
- **Grounding**: Evidence-based answer validation
- **Integration**: Contract boundaries between components
- **Memory**: Profile retrieval, usage, and correctness

#### Multi-turn Evaluation

- **Turn-level**: Success, item match, exclusion compliance, reference correctness
- **Conversation-level**: Turn success rate, conversation success, context retention
- **Session Isolation**: Independent sessions do not share state
- **Context Persistence**: Session state persists across turns correctly

#### Campaign Orchestration

- **Experiment Matrix**: Multiple experiments in a single campaign
- **Shared Cases**: Same evaluation cases across experiments for fair comparison
- **Checkpoint/Resume**: Interrupted campaigns can be resumed
- **Statistical Comparison**: Bootstrap CIs and significance tests
- **Aggregation**: Metrics aggregated across runs and experiments

### Key Classes

- `BenchmarkCase`: Case definition for component benchmarks
- `BenchmarkResult`: Result of running a single benchmark case
- `BenchmarkSummary`: Aggregated results for a component benchmark
- `RegressionReport`: Comparison between baseline and current run
- `ComponentEvaluator`: Base class for component evaluators
- `Conversation`: Multi-turn conversation definition
- `ConversationResult`: Result of evaluating a conversation
- `CampaignConfig`: Campaign configuration with experiment matrix
- `CampaignResult`: Result of running a full campaign

### Provenance Tracking

Every evaluation run tracks:
- Git commit SHA
- Source fingerprint (hash of implementation files)
- Environment versions (Python, numpy, pandas, etc.)
- Hardware info
- Timestamp
- Random seed
- Dataset version

This ensures reproducibility and traceability of all results.
