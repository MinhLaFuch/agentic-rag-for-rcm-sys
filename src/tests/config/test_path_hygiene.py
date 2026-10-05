"""Guards for the config/path architecture: tunables in YAML, fixed contracts in Python, one path source."""

import ast

from package.config._constants import PROJECT_ROOT

PY_ROOTS = [PROJECT_ROOT / "package", PROJECT_ROOT / "scripts" / "py"]


def _py_files():
    for root in PY_ROOTS:
        yield from (p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def test_no_hardcoded_project_dirs_in_code():
    # Directories come from DataPaths (configs/data_paths.yaml). Docstrings/comments may mention them.
    offenders = []
    for path in _py_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                v = node.value
                if v == "experiments" or v.startswith(("experiments/", "resource/")) or v == "resource":
                    offenders.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}: {v!r}")
    assert not offenders, "hard-coded project paths:\n" + "\n".join(offenders)


def test_shell_scripts_do_not_rebuild_data_paths_by_hand():
    offenders = [
        p.name for p in (PROJECT_ROOT / "scripts" / "sh").glob("*.sh") if "data_paths.paths." in p.read_text(encoding="utf-8")
    ]
    assert not offenders, f"use `data_path <name>` (DataPaths) instead of cfg data_paths.paths.*: {offenders}"


def test_no_config_py_modules_left():
    # `_config.py` used to mix tunables, schema and dead code. Now: tunables -> configs/*.yaml,
    # fixed contracts -> _schema.py (or _constants.py for bootstrap constants).
    assert not list((PROJECT_ROOT / "package").rglob("_config.py"))


def test_no_literal_secrets_in_configs():
    import re

    for path in (PROJECT_ROOT / "configs").glob("*.yaml"):
        assert not re.search(r"\bsk-[A-Za-z0-9_-]{16,}", path.read_text(encoding="utf-8")), path.name
