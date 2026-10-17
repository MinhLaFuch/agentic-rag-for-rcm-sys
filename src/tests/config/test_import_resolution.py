"""Static test that all package.* imports resolve to existing modules.

This test catches bugs like the one in Phase 1a where scripts/experiments/compare_experiments.py
imported from a non-existent path package.agents.evaluation.ablation.
"""

import ast
from pathlib import Path

from package.config._constants import PROJECT_ROOT

PY_ROOTS = [PROJECT_ROOT / "package", PROJECT_ROOT / "scripts", PROJECT_ROOT / "tests"]


def _py_files():
    for root in PY_ROOTS:
        yield from (p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _module_file_exists(module_name: str) -> bool:
    """Check if a module's file exists in the filesystem.
    
    This is more reliable than trying to import, which can fail for many reasons
    unrelated to the module not existing.
    """
    # Convert module name to file path
    parts = module_name.split(".")
    if parts[0] != "package":
        return True  # Only check package.* imports
    
    # Build the path
    base_path = PROJECT_ROOT / "package"
    for i, part in enumerate(parts[1:], 1):
        # Check if this is a file (last part) or directory
        if i == len(parts) - 1:
            # Last part could be a file
            potential_file = base_path / f"{part}.py"
            if potential_file.exists():
                return True
            # Or could be a package (directory with __init__.py)
            potential_dir = base_path / part
            if potential_dir.is_dir() and (potential_dir / "__init__.py").exists():
                return True
        else:
            # Middle parts must be directories
            base_path = base_path / part
            if not base_path.is_dir() or not (base_path / "__init__.py").exists():
                return False
    
    return base_path.exists()


def _extract_imports(tree: ast.AST) -> list[tuple[str, int]]:
    """Extract all module imports from an AST tree.
    
    Returns list of (module_name, lineno). For 'from X import Y', returns X.
    """
    imports = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            # For 'from' imports, check the module being imported from
            if node.module:
                imports.append((node.module, node.lineno))
    
    return imports


def test_all_package_imports_have_existing_files():
    """Ensure all package.* imports in package/, scripts/, tests/ point to existing files."""
    offenders = []
    
    for path in _py_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports = _extract_imports(tree)
            
            for module_name, lineno in imports:
                # Only check package.* imports
                if module_name.startswith("package."):
                    if not _module_file_exists(module_name):
                        rel_path = path.relative_to(PROJECT_ROOT)
                        offenders.append(f"{rel_path}:{lineno}: from {module_name}")
        except SyntaxError:
            # Skip files with syntax errors (they'll be caught by other tests)
            continue
    
    assert not offenders, "Imports to non-existent package modules:\n" + "\n".join(offenders)
