"""Pytest fixtures for component benchmarks."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def fake_jev_provider():
    """
    Mock httpx.Client to provide a fake Jev provider for component benchmarks.

    This allows component benchmarks to use Jev without real API calls.
    The fixture returns a mock client that can be configured per test if needed.
    """
    with patch("httpx.Client") as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Default mock response for Jev evaluation
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answers": {
                "claim_0": {"noul": 0.9, "confidence": 0.95},
            },
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        mock_client.post.return_value = mock_response

        yield mock_client
