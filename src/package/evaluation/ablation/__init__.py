"""Ablation comparison tool (base template)."""

from ._compare import compare_two_groups, find_disagreements, pair_by_request_id
from ._limits import get_ablation_limits
from ._loader import load_group_data, validate_contrast_config
from ._report import render_markdown_report, write_csv, write_disagreements, write_json
from ._statistics import bootstrap_ci, mcnemar_test

__all__ = [
    "compare_two_groups",
    "find_disagreements",
    "pair_by_request_id",
    "get_ablation_limits",
    "load_group_data",
    "validate_contrast_config",
    "render_markdown_report",
    "write_csv",
    "write_disagreements",
    "write_json",
    "bootstrap_ci",
    "mcnemar_test",
]
