"""Shared fixtures. Every test that touches `resource/` goes through `resource_root`
so nothing ever reads or writes the real repo."""

import gzip
import json

import pytest

from package.utils.path import RESOURCE_DIR_ENV_VAR, WORKSPACE_ENV_VAR


@pytest.fixture
def resource_root(tmp_path, monkeypatch):
    """Redirect `resource/` to a temp dir and clear any workspace override."""
    root = tmp_path / "resource"
    root.mkdir()
    monkeypatch.setenv(RESOURCE_DIR_ENV_VAR, str(root))
    monkeypatch.delenv(WORKSPACE_ENV_VAR, raising=False)
    return root


@pytest.fixture
def write_jsonl_gz():
    """Return a helper: write_jsonl_gz(path, records) -> path (creates parent dirs)."""

    def _write(path, records):
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wt", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return path

    return _write
