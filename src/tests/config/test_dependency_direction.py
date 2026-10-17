"""Static guard for the dependency direction between the top-level packages (Rule 7 in the refactor task).

    tools      -> must not import agents
    agents     -> must not import inference / demo / evaluation
    inference  -> may import agents (not demo / evaluation)
    evaluation -> may import agents / inference (not demo)
    demo       -> may import agents / inference (not evaluation)

Only ``package/`` is checked; ``scripts/`` are entry points and ``tests/`` are white-box, both are exempt.
"""

from __future__ import annotations

from tests.config.test_package_layout import PACKAGE_ROOT, PROJECT_ROOT, _dotted_module, _imported_modules, _py_files

FORBIDDEN_IMPORTS = {
    "package.tools": ("package.agents",),
    "package.agents": ("package.inference", "package.demo", "package.evaluation"),
    "package.inference": ("package.demo", "package.evaluation"),
    "package.evaluation": ("package.demo",),
    "package.demo": ("package.evaluation",),
}

# (importing file, imported package) pairs that are allowed on purpose.
ALLOWED_EXCEPTIONS: set[tuple[str, str]] = set()


def _is_under(dotted: str, package: str) -> bool:
    return dotted == package or dotted.startswith(package + ".")


def _owner_package(importer: str) -> str | None:
    return next((p for p in FORBIDDEN_IMPORTS if _is_under(importer, p)), None)


def test_dependency_direction():
    offenders = []
    for path in _py_files(PACKAGE_ROOT):
        owner = _owner_package(_dotted_module(path))
        if owner is None:
            continue
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        for dotted, lineno in _imported_modules(path):
            for forbidden in FORBIDDEN_IMPORTS[owner]:
                if _is_under(dotted, forbidden) and not any(
                    rel == file and _is_under(dotted, allowed) for file, allowed in ALLOWED_EXCEPTIONS
                ):
                    offenders.append(f"{rel}:{lineno}: {owner} must not import {dotted}")
    assert not offenders, "dependency-direction violations:\n" + "\n".join(sorted(set(offenders)))


def test_allowed_exceptions_are_still_needed():
    """An exception that nothing uses any more must be deleted, so the list cannot rot."""
    used = set()
    for path in _py_files(PACKAGE_ROOT):
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        for dotted, _ in _imported_modules(path):
            used.update((rel, allowed) for file, allowed in ALLOWED_EXCEPTIONS if rel == file and _is_under(dotted, allowed))
    assert used == ALLOWED_EXCEPTIONS
