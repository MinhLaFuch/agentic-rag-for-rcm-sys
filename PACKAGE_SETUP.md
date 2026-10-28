# Setting Up the Project

This repo uses an **editable install** so that anything under `src/` (e.g. `package`, `config`, etc.) can be imported directly in notebooks and scripts — no `PYTHONPATH` or `sys.path` hacks needed.

## 1. Set up your environment

Make sure you're using **Python 3.12+**, in a dedicated venv/conda env for this project's own code — **not** the same environment you use for anything under `forked_repository/` (those are separate repos with their own dependencies and should stay isolated).

From the **repo root**:

```bash
# example with venv
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
```

## 2. Install the package in editable mode

From the **repo root** (same folder as `pyproject.toml`, `.gitignore`, `README.md`):

```bash
pip install -e .
```

This reads `pyproject.toml`, discovers everything under `src/` as importable packages, and links it into your environment — so `import package.memory.memory_tool` (etc.) works from anywhere, without needing to be in a specific folder or set `PYTHONPATH`.

> If you get an error here, double check you're running this from the repo root, not from inside `src/`.

## 3. Point your Jupyter kernel at the right environment

If you're using notebooks (VS Code or Jupyter), make sure the kernel selected is the **same environment** you just ran `pip install -e .` in. In VS Code, this is shown in the top-right of the notebook (e.g. `.venv (3.12.0)`).

If you installed the package *after* the kernel was already running, **restart the kernel** — editable installs aren't picked up by an already-running kernel.

## 4. Verify it works

Run this in any notebook or script:

```python
from package.memory.memory_tool import MemoryTool
```

If it resolves without a `ModuleNotFoundError`, you're set.

## Running Scripts

After installing in editable mode, you can run scripts from anywhere without setting `PYTHONPATH`:

```bash
# From repo root
python -m package.evaluation.component.run --component memory_correctness --dataset package/evaluation/component/benchmarks/memory_correctness_dataset.jsonl

# Or with pytest (pythonpath is configured in pyproject.toml)
pytest
```

No need for `$env:PYTHONPATH = 'src'` or similar commands.

## Notes

- **Do not** run `pip install -e .` inside the venvs used for `forked_repository/AgentCF` or `forked_repository/RecAI` — those are separate submodules with their own dependency setups and should not be mixed with this package.
- If you add a new folder under `src/` and want it importable (e.g. `src/utils/`), just add an `__init__.py` inside it — no changes to `pyproject.toml` needed, setuptools will auto-discover it next time you reinstall (`pip install -e .` again).
- The `pyproject.toml` is in the repo root (not in `src/`), and the `[tool.setuptools.packages.find]` section points to `src/` as the package source.
