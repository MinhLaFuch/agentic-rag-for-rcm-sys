"""Pytest configuration: shared fixtures + per-test input/output results file (see results_report.py)."""

from tests.results_report import pytest_addoption, pytest_configure  # noqa: F401  (pytest hooks)
from tests.tools_helpers import corpus, cf_setup  # noqa: F401  (shared fixtures)
