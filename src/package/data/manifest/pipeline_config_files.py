"""List configuration files whose contents define a pipeline stage."""

from pathlib import Path

from ._helper import _config_files


def pipeline_config_files(stage: str) -> list[Path]:
    return _config_files(stage)

