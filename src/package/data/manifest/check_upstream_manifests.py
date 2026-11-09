"""Validate a stage's prior manifest chain against its actual input artifacts."""

from pathlib import Path

from ._helper import _check_upstream


def check_upstream_manifests(
    manifests: list[Path], expected_inputs: list[list[Path]], *, allow_mismatch: bool = False
) -> list[str]:
    return _check_upstream(manifests, expected_inputs, allow_mismatch=allow_mismatch)

