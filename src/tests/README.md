# Tests

This directory contains all tests for the project.

## Test Categories

### Unit Tests
- Tests that mock external dependencies (LLM, data, network)
- Fast, deterministic, no external requirements
- Can run in CI without any setup
- Examples: test_memory_tool.py, test_phase1_smoke.py

### Integration Tests
- Tests that use real components but synthetic/test data
- Slower than unit tests, require component wiring
- Marked with `@pytest.mark.integration`
- Examples: test_plan_executor.py, test_tools_integration.py
- Run with: `pytest -m integration`
- Skip with: `pytest -m "not integration"`

### Real Smoke Tests
- Tests that require real external resources (LLM, real data)
- Intended to validate real integrations work
- Not run in CI by default
- Examples: jev_smoke_test.py, smoke_real_llm.py
- These are scripts in scripts/ directory, not pytest tests

## Running Tests

Run all tests (excluding integration):
```bash
pytest
```

Run integration tests only:
```bash
pytest -m integration
```

Run all tests including integration:
```bash
pytest -m ""
```

Run specific test files:
```bash
pytest tests/corpus/test_contract_corpus.py
```

## Test Fixtures

Test fixtures are organized by component:
- `tests/corpus/conftest.py` - Corpus-related fixtures
- `tests/recommenders/conftest.py` - Recommender fixtures
- `tests/scoring/conftest.py` - Scoring fixtures
- `tests/sql/conftest.py` - SQL fixtures

The `World` fixture provides a minimal test corpus with:
- 6 items across Games and Toys domains
- Sparse matrices for history
- Test scenarios for cold/warm users
