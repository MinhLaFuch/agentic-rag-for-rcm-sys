"""Static guards for the package layout conventions (Rule 4 and Rule 6 in the refactor task).

1. Atomic files: every public module (not ``_*``, ``__init__``, ``__main__``) under ``package/`` holds exactly ONE
   public top-level class/function, and its name equals the file stem (underscores ignored, case-insensitive:
   ``ItemCFTool`` <-> ``item_cf_tool.py``).
2. Privacy: a ``_``-prefixed module is internal to the folder that contains it. Nothing outside that folder
   (``package/`` and ``scripts/`` are checked, ``tests/`` is exempt) may import it; cross-folder access goes through
   the folder's ``__init__.py`` re-exports or a public module.
"""

from __future__ import annotations

import ast
from pathlib import Path


from package.config._constants import PROJECT_ROOT

PACKAGE_ROOT = PROJECT_ROOT / "package"
CHECKED_ROOTS = [PACKAGE_ROOT, PROJECT_ROOT / "scripts"]  # tests/ may import privates (white-box tests)
SKIPPED_STEMS = {"__init__", "__main__"}


def _py_files(root: Path):
    yield from (p for p in sorted(root.rglob("*.py")) if "__pycache__" not in p.parts)


def _norm(name: str) -> str:
    return name.replace("_", "").lower()


# ----------------------------------------------------------------------------------------------- rule 6 + naming


def _public_top_level(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_")
    ]


def test_every_public_module_has_one_public_symbol_named_after_the_file():
    offenders = []
    for path in _py_files(PACKAGE_ROOT):
        if path.stem.startswith("_") or path.stem in SKIPPED_STEMS:
            continue
        symbols = _public_top_level(path)
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        if len(symbols) != 1:
            offenders.append(f"{rel}: expected exactly 1 public class/function, found {symbols or 'none'}")
        elif _norm(symbols[0]) != _norm(path.stem):
            offenders.append(f"{rel}: public symbol {symbols[0]!r} does not match the file name")
    assert not offenders, "atomic-file / name-match violations:\n" + "\n".join(offenders)


def test_public_names_are_unique_across_the_package():
    seen: dict[str, str] = {}
    duplicates = []
    for path in _py_files(PACKAGE_ROOT):
        if path.stem.startswith("_") or path.stem in SKIPPED_STEMS:
            continue
        for name in _public_top_level(path):
            rel = path.relative_to(PROJECT_ROOT).as_posix()
            if name in seen:
                duplicates.append(f"{name}: {seen[name]} and {rel}")
            seen.setdefault(name, rel)
    assert not duplicates, "duplicate public names:\n" + "\n".join(duplicates)


# ----------------------------------------------------------------------------------------------- rule 4 (privacy)


def _dotted_module(path: Path) -> str:
    """package/a/b.py -> 'package.a.b'; package/a/__init__.py -> 'package.a'."""
    parts = list(path.relative_to(PROJECT_ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _module_exists(dotted: str) -> bool:
    base = PROJECT_ROOT.joinpath(*dotted.split("."))
    return base.with_suffix(".py").is_file() or (base / "__init__.py").is_file()


def _imported_modules(path: Path) -> list[tuple[str, int]]:
    """Absolute dotted names of every module a file imports (relative imports resolved), with line numbers."""
    importer = _dotted_module(path)
    importer_pkg = importer if path.stem == "__init__" else importer.rpartition(".")[0]
    found: list[tuple[str, int]] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                anchor = importer_pkg.split(".")
                anchor = anchor[: len(anchor) - (node.level - 1)]
                base = ".".join(anchor + ([node.module] if node.module else []))
            else:
                base = node.module or ""
            if not base:
                continue
            found.append((base, node.lineno))
            # `from pkg import _private_module` imports a module too
            found.extend((f"{base}.{alias.name}", node.lineno) for alias in node.names if _module_exists(f"{base}.{alias.name}"))
    return found


def _private_owner(dotted: str) -> str | None:
    """For 'package.api._error' return the owning folder 'package.api'; None if no private component."""
    parts = dotted.split(".")
    for index, part in enumerate(parts):
        if part.startswith("_") and not part.startswith("__"):
            return ".".join(parts[:index])
    return None


def test_no_module_imports_a_private_module_of_another_folder():
    offenders = []
    for root in CHECKED_ROOTS:
        for path in _py_files(root):
            importer = _dotted_module(path)
            for dotted, lineno in _imported_modules(path):
                if not dotted.startswith("package.") or not _module_exists(dotted):
                    continue
                owner = _private_owner(dotted)
                if owner is None:
                    continue
                inside_owner = importer == owner or importer.startswith(owner + ".")
                if not inside_owner:
                    offenders.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}:{lineno}: imports {dotted}")
    assert not offenders, "cross-folder imports of `_` modules:\n" + "\n".join(sorted(set(offenders)))
