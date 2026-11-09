"""Test grounding benchmark with fake Jev provider."""

from __future__ import annotations

import os
from unittest.mock import Mock, patch

import pytest

pytestmark = pytest.mark.integration

from package.evaluation.component.benchmarks.grounding_benchmark import GroundingBenchmark


def test_grounding_benchmark_with_fake_jev():
    """Test grounding benchmark end-to-end with mocked Jev provider."""
    # Set fake API key for config expansion
    os.environ["TYPESAFE_API_KEY"] = "fake_test_key"

    with patch("httpx.Client") as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Mock Jev response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answers": {
                "claim_0": {"noul": 0.9, "confidence": 0.95},
                "claim_1": {"noul": 0.8, "confidence": 0.9},
            },
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        mock_client.post.return_value = mock_response

        benchmark = GroundingBenchmark(config={"use_jev": True})

        case_input = {
            "case_id": "grounding_001",
            "input": {
                "user_request": "I want an action game",
                "evidence": [
                    {"item_id": "vg_001", "title": "Action Game", "main_category": "Action", "price": 30.0}
                ],
            },
            "expected": {
                "claims_supported": 1,
                "total_claims": 1,
                "grounding_rate": 1.0,
                "hallucination_rate": 0.0,
            },
        }

        actual_output = benchmark.run_component(case_input["input"])
        metrics = benchmark.score_component(actual_output, case_input["expected"])

        # Verify Jev was called and produced results
        assert "jev_result" in actual_output
        assert actual_output["jev_result"]["evaluation_state"] == "success"
        assert actual_output["jev_result"]["total_claims"] > 0  # Realistic answer produces claims

        # Verify metrics are computed
        assert metrics["total_claims"] > 0
        assert 0.0 <= metrics["grounding_rate"] <= 1.0
