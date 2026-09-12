# Setting Up the `src` Package

This repo uses an **editable install** so that anything under `src/` (e.g. `config`, `data`, etc.) can be imported directly in notebooks and scripts — no `sys.path` hacks needed.

## 1. Set up your environment

Make sure you're using **Python 3.12+**, in a dedicated venv/conda env for this project's own code (`src/`) — **not** the same environment you use for anything under `forked_repository/` (those are separate repos with their own dependencies and should stay isolated).

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

This reads `pyproject.toml`, discovers everything under `src/` as importable packages, and links it into your environment — so `import config.data` (etc.) works from anywhere, without needing to be in a specific folder.

> If you get an error here, double check you're running this from the repo root, not from inside `src/`.

## 3. Point your Jupyter kernel at the right environment

If you're using notebooks (VS Code or Jupyter), make sure the kernel selected is the **same environment** you just ran `pip install -e .` in. In VS Code, this is shown in the top-right of the notebook (e.g. `.venv (3.12.0)`).

If you installed the package *after* the kernel was already running, **restart the kernel** — editable installs aren't picked up by an already-running kernel.

## 4. Verify it works

Run this in any notebook or script:

```python
from config.data import AMAZON_RAW_DIR, AMAZON_PREPROCESSED_DIR
```

If it resolves without a `ModuleNotFoundError`, you're set.

## Notes

### Choosing the repository source

Data paths use the main repository by default. To use a fork under
`forked_repository/`, select it explicitly when constructing `PathConfig`:

```python
from local_package.config import PathConfig

paths = PathConfig(__file__, source="main")
forked_paths = PathConfig(__file__, source="forked", forked_repository="RecAI")
```

For notebooks, the same choice can be set without changing code:

```bash
export LOCAL_PACKAGE_REPOSITORY=forked
export LOCAL_PACKAGE_FORKED_REPOSITORY=RecAI
```

The supported source values are `main` and `forked`. A fork may provide its
data under either `resource/` or `src/resource/`.

- **Do not** run `pip install -e .` inside the venvs used for `forked_repository/AgentCF` or `forked_repository/RecAI` — those are separate submodules with their own dependency setups and should not be mixed with this package.
- If you add a new folder under `src/` and want it importable (e.g. `src/utils/`), just add an `__init__.py` inside it — no changes to `pyproject.toml` needed, setuptools will auto-discover it next time you reinstall (`pip install -e .` again).
