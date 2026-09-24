"""Smoke test: every name a package advertises in `__all__` must actually import.

Catches broken re-exports (renamed functions, moved folders) before any behaviour test runs.
"""

import importlib

import pytest

PACKAGES = [
    "package.data",
    "package.data.clean",
    "package.data.eda",
    "package.data.save",
    "package.data.filter",
    "package.data.leakage",
    "package.data.loader",
    "package.data.train",
    "package.data.utils",
    "package.utils",
    "package.utils.log",
    "package.utils.path",
]


@pytest.mark.parametrize("module_name", PACKAGES)
def test_all_names_in___all___resolve(module_name):
    module = importlib.import_module(module_name)
    assert module.__all__, f"{module_name} has an empty __all__"
    missing = [name for name in module.__all__ if not hasattr(module, name)]
    assert not missing, f"{module_name}.__all__ lists names that do not exist: {missing}"


@pytest.mark.parametrize("module_name", PACKAGES)
def test_all_has_no_duplicates(module_name):
    names = importlib.import_module(module_name).__all__
    assert len(names) == len(set(names))