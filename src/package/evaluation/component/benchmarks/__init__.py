"""Benchmark implementations for specific components."""

from __future__ import annotations

from ._dataset_common import DATASET_PATH, SPECS
from .analyze import analyze
from .analyze_metric import analyze_metric
from .build_cases import build_cases
from .build_memory_correctness_dataset import DATASET_PATH, SPECS, build_cases, render
from .collect import collect
from .compute_memory_oracle import DEFAULT_RECENT_N, compute_memory_oracle
from .controlled_filter_tool import ControlledFilterTool
from .controlled_similar_tool import ControlledSimilarTool
from .create_test_corpus import create_test_corpus
from .create_test_interactions import create_test_interactions
from .create_test_mappings import create_test_mappings
from .create_test_meta import create_test_meta
from .default_metrics import default_metrics
from .executor_benchmark import ExecutorBenchmark
from .get_controlled_tools import get_controlled_tools
from .get_interactions_without_rating import get_interactions_without_rating
from .get_mock_llm import get_mock_llm
from .get_mock_tools import get_mock_tools
from .grounding_benchmark import GroundingBenchmark
from .integration_benchmark import IntegrationBenchmark
from .leakage_probe import leakage_probe
from .mock_filter_tool import MockFilterTool
from .mock_llm_provider import MockLLMProvider
from .mock_rank_tool import MockRankTool
from .mock_search_tool import MockSearchTool
from .mock_similar_tool import MockSimilarTool
from .planner_benchmark import PlannerBenchmark
from .render import render
from .render_markdown import render_markdown
from .scope_of import scope_of

# Test compatibility modules (publicly accessible for tests/ directory)
from . import build_memory_correctness_dataset
from . import memory_correctness_setup
from . import memory_oracle

__all__ = [
    "DATASET_PATH",
    "SPECS",
    "PlannerBenchmark",
    "ExecutorBenchmark",
    "GroundingBenchmark",
    "IntegrationBenchmark",
    "ControlledFilterTool",
    "ControlledSimilarTool",
    "get_controlled_tools",
    "build_cases",
    "render",
    "create_test_interactions",
    "create_test_corpus",
    "create_test_meta",
    "create_test_mappings",
    "get_interactions_without_rating",
    "compute_memory_oracle",
    "DEFAULT_RECENT_N",
    "leakage_probe",
    "default_metrics",
    "scope_of",
    "collect",
    "analyze_metric",
    "analyze",
    "render_markdown",
    "MockLLMProvider",
    "get_mock_llm",
    "MockFilterTool",
    "MockSearchTool",
    "MockSimilarTool",
    "MockRankTool",
    "get_mock_tools",
    # Test compatibility (tests/ directory is exempt from private import rules)
    "build_memory_correctness_dataset",
    "memory_correctness_setup",
    "memory_oracle",
]
