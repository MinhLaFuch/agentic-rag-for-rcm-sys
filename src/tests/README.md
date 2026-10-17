# Tests Organization

This directory contains all test files organized by module category for better navigation and maintainability.

## Directory Structure

### 📁 `agents/`
Tests for agent-related functionality including evaluation, ablation studies, and inference.

**Subdirectories:**
- **`ablation/`** - Tests for ablation experiment comparison and analysis
- **`evaluation/`** - Tests for agent evaluation logic and adapters
- **`inference/`** - Tests for inference adapters and composition

**Root-level tests:**
- `test_agent_eval.py` - Agent evaluation integration tests
- `test_baselines.py` - Baseline model tests
- `test_item_knn_equivalence.py` - ItemKNN equivalence tests
- `test_llm_provider.py` - LLM provider configuration tests
- `test_memory_tool.py` - MemoryTool functionality tests
- `test_phase1_smoke.py` - Phase 1 smoke tests
- `test_plan_executor.py` - PlanExecutor tests
- `test_plan_reflect.py` - Plan reflection mechanism tests

---

### 📁 `config/`
Tests for configuration loading, path management, and domain registry.

- `test_config_loader.py` - Configuration loading tests
- `test_data_paths.py` - Data path resolution tests
- `test_dependency_direction.py` - Dependency direction between top-level packages (tools, agents, inference, evaluation, demo)
- `test_domain_registry.py` - Domain registry tests
- `test_package_layout.py` - Atomic files, file/symbol name match, `_` modules private to their folder
- `test_path_hygiene.py` - Path hygiene validation tests
- `test_tool_limits.py` - Tool limits configuration tests

---

### 📁 `data/`
Tests for data processing, cleaning, EDA, splitting, and leakage checks.

- `test_clean.py` - Data cleaning tests
- `test_diagnose_splits.py` - Split diagnosis tests
- `test_eda.py` - Exploratory data analysis tests
- `test_eval_helpers.py` - Evaluation helper function tests
- `test_leakage_check.py` - Data leakage detection tests
- `test_load_item_metadata.py` - Item metadata loading tests
- `test_load_splits.py` - Split loading tests
- `test_mapping.py` - ID mapping tests
- `test_metadata_eda.py` - Metadata EDA tests
- `test_split_paths.py` - Split path validation tests
- `test_streaming_eda.py` - Streaming EDA tests
- `test_temporal_split.py` - Temporal split tests

---

### 📁 `demo/`
Tests for demo UI and backend functionality.

- `test_demo_backend.py` - Demo backend tests
- `test_demo_config.py` - Demo configuration tests
- `test_gradio_ui.py` - Gradio UI tests
- `test_inference_adapter.py` - Inference adapter tests
- `test_live_backend.py` - Live backend tests

---

### 📁 `tools/`
Tests for recommendation tools organized by functionality.

**Subdirectories:**
- **`base/`** - Base tool class and validation tests
- **`corpus/`** - ItemCorpus and corpus-related tests
- **`evaluation/`** - Tool evaluation framework tests
- **`integration/`** - Tool integration tests
- **`ranking/`** - Ranking tools (ItemCF, RecoModel) tests
- **`recommenders/`** - Recommender model tests
- **`retrieval/`** - Retrieval tools (SemanticSearch) tests
- **`score/`** - Scoring tools tests
- **`sql_query/`** - SQL query tool tests
- **`utilities/`** - Utility function tests

---

### Root-level tests
- `test_package_import.py` - Package import validation tests
- `conftest.py` - Shared pytest fixtures and configuration
- `run_all_tests.sh` / `run_all_tests.bat` - Scripts to run all tests
- `results_report.py` - Test results reporting utility

---

## Running Tests

### Run all tests
```bash
# From project root
pytest tests/

# With verbose output
pytest tests/ -v

# With coverage
pytest tests/ --cov=package
```

### Run specific category
```bash
# Run only agent tests
pytest tests/agents/

# Run only tool tests
pytest tests/tools/

# Run only data tests
pytest tests/data/
```

### Run specific test file
```bash
pytest tests/agents/test_plan_executor.py
pytest tests/tools/ranking/test_item_cf_tool.py
```

### Run tests with markers (if configured)
```bash
# Run only fast tests
pytest tests/ -m fast

# Run only integration tests
pytest tests/ -m integration
```

## Test Organization Notes

- Tests mirror the package structure for easy navigation
- Each subdirectory has its own `conftest.py` for category-specific fixtures
- Shared fixtures are in the root `conftest.py`
- Integration tests are separated from unit tests where appropriate
- Test files follow the naming convention: `test_<module>.py`
- Test logs are written to `experiments/test_logs/` (not version-controlled)

## Test Coverage

The test suite covers:
- Unit tests for individual components
- Integration tests for tool interactions
- End-to-end tests for agent workflows
- Regression tests for known issues
- Contract tests for tool interfaces
