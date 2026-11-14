"""_source_fingerprint must actually cover src/package + src/configs.

Regression for the parents[5] bug: the fingerprint used to hash only
pyproject.toml because package/scripts/configs were looked up at the repo
root (they live under src/), so code drift was invisible to resume.
"""

from __future__ import annotations

from pathlib import Path

from package.evaluation.recommender.experiment.save_experiment import _source_fingerprint

SRC = Path(__file__).parents[3]


def test_fingerprint_covers_package_sources():
    """Fingerprint differs from a pyproject-only digest -> package is hashed."""
    import hashlib

    repo_pyproject = SRC.parent / "pyproject.toml"
    only = hashlib.sha256()
    only.update(repo_pyproject.read_bytes())
    assert _source_fingerprint() != only.hexdigest()


def test_fingerprint_stable_across_calls():
    assert _source_fingerprint() == _source_fingerprint()


def test_package_file_change_changes_fingerprint():
    probe = SRC / "package" / "_fingerprint_probe_tmp.py"
    assert not probe.exists()
    try:
        before = _source_fingerprint()
        probe.write_text("X = 1\n", encoding="utf-8")
        assert _source_fingerprint() != before
    finally:
        probe.unlink(missing_ok=True)


def test_unrelated_file_does_not_change_fingerprint():
    # experiments/ is outside package/scripts/configs and not .py/.yaml there
    probe = SRC / "experiments" / "_fingerprint_probe_tmp.py"
    probe.parent.mkdir(parents=True, exist_ok=True)
    try:
        before = _source_fingerprint()
        probe.write_text("X = 1\n", encoding="utf-8")
        assert _source_fingerprint() == before
    finally:
        probe.unlink(missing_ok=True)
