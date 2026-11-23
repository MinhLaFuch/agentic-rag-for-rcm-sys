"""Reporting package.

`_adapter.build_report_results` converts real `run_agent_eval` outputs
(scored rows + trajectories) into the flat ``results`` shape consumed by
`_generator` (markdown/CSV/failure reports) and `_visualizations` (SVG
charts). `scripts/evaluation/run_agent_eval.py` writes report.md,
report.csv, failures.md and charts/ into every experiment dir.

`scripts/evaluation/generate_example_report.py` remains a synthetic,
DO-NOT-CITE demo of the same API surface.
"""

from ._adapter import build_report_results
from ._generator import (
    generate_markdown_report,
    generate_csv_export,
    generate_failure_report,
    generate_comparison_report,
)

from ._visualizations import (
    generate_layer_comparison_chart,
    generate_request_kind_heatmap,
    generate_retrieval_funnel_chart,
    generate_latency_distribution_chart,
    generate_multi_turn_performance_chart,
    generate_all_charts,
)

__all__ = [
    "build_report_results",
    "generate_markdown_report",
    "generate_csv_export",
    "generate_failure_report",
    "generate_comparison_report",
    "generate_layer_comparison_chart",
    "generate_request_kind_heatmap",
    "generate_retrieval_funnel_chart",
    "generate_latency_distribution_chart",
    "generate_multi_turn_performance_chart",
    "generate_all_charts",
]
