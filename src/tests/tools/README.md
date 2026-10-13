# Tests for `package/tools`

Run from the repository root with the project's virtual-environment interpreter (not a global `python`/`pip`):

    python -m pytest tests/tools -q                      # every standalone tool test (this folder is the single home of package/tools tests)
    python -m pytest tests/agent -q                      # agent tests (PlanExecutor, LLM provider, MemoryTool, evaluation, ...)
    python -m pytest tests -q                            # everything

or `tests/tools/run_tests.sh` / `run_tests.bat` (log + per-test input/output file in `tests/logs/`, like the other folders).

Layout: `conftest.py` holds the shared deterministic "tiny world" fixture (read its docstring first: every expected
number in these tests is hand-derived from it). One `test_contract_*.py` per module, plus
`integration/test_tools_integration.py` for the module-boundary pipelines.

Besides the `test_contract_*.py` files, each folder holds the former `tests/agent/tools` regression/hardening tests
(`test_*_hardening.py`, `test_*_regressions.py`, ...). Those use the shared `corpus` / `cf_setup` fixtures from
`tests/tools_helpers.py` (5-item corpus, registered in `tests/conftest.py`), not the `world` fixture of this folder's conftest.
