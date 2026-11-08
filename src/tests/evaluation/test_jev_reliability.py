"""Tests for Jev (LLM-as-a-judge) reliability with fake provider."""

from __future__ import annotations

import os
from unittest.mock import Mock, patch

import pytest

from package.api import JevProvider
from package.evaluation.product_reply.evaluate_product_reply_with_jev import evaluate_product_reply_with_jev


class TestJevProviderFake:
    """Test JevProvider with mocked HTTP client to avoid real API calls."""

    def test_jev_provider_fake_success(self):
        """Test successful Jev evaluation with mocked response."""
        with patch("httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            # Mock successful POST response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "answers": {
                    "default": {
                        "noul": 0.9,
                        "confidence": 0.95,
                    }
                },
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }
            mock_client.post.return_value = mock_response

            provider = JevProvider(api_key="fake_key", base_url="https://fake.api")
            result, usage = provider.evaluate_noul(
                state="test state",
                instructions="Is this supported?",
            )

            assert result["answers"]["default"]["noul"] == 0.9
            assert usage["input_tokens"] == 10
            mock_client.post.assert_called_once()
            provider.close()

    def test_jev_provider_exception(self):
        """Test that provider exceptions are propagated."""
        with patch("httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            # Mock HTTP error
            mock_client.post.side_effect = Exception("Network error")

            provider = JevProvider(api_key="fake_key", base_url="https://fake.api")

            with pytest.raises(Exception, match="Network error"):
                provider.evaluate_noul(
                    state="test state",
                    instructions="Is this supported?",
                )

            provider.close()

    def test_jev_provider_missing_api_key(self):
        """Test that missing API key raises ValueError."""
        # Clear env var
        original = os.environ.get("TYPESAFE_API_KEY")
        os.environ.pop("TYPESAFE_API_KEY", None)

        try:
            with pytest.raises(ValueError, match="TYPESAFE_API_KEY not set"):
                JevProvider(api_key=None)
        finally:
            if original is not None:
                os.environ["TYPESAFE_API_KEY"] = original

    def test_env_var_expansion(self):
        """Test that env var is used when api_key is None."""
        original = os.environ.get("TYPESAFE_API_KEY")
        os.environ["TYPESAFE_API_KEY"] = "test_key_from_env"

        try:
            with patch("httpx.Client") as mock_client_class:
                mock_client = Mock()
                mock_client_class.return_value = mock_client

                provider = JevProvider(api_key=None)
                assert provider.api_key == "test_key_from_env"
                provider.close()
        finally:
            if original is not None:
                os.environ["TYPESAFE_API_KEY"] = original
            else:
                os.environ.pop("TYPESAFE_API_KEY", None)

    def test_malformed_response(self):
        """Test handling of malformed JSON response."""
        with patch("httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            # Mock response with invalid JSON
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_client.post.return_value = mock_response

            provider = JevProvider(api_key="fake_key", base_url="https://fake.api")

            with pytest.raises(ValueError, match="Invalid JSON"):
                provider.evaluate_noul(
                    state="test state",
                    instructions="Is this supported?",
                )

            provider.close()


class TestEvaluateProductReplyWithJev:
    """Test evaluate_product_reply_with_jev with mocked Jev provider."""

    def test_evaluate_with_mocked_jev_success(self):
        """Test successful evaluation with mocked Jev."""
        with patch("package.evaluation.product_reply.evaluate_product_reply_with_jev.JevProvider") as mock_provider_class:
            mock_provider = Mock()
            mock_provider_class.return_value = mock_provider

            # Mock faithfulness evaluation
            mock_provider.evaluate.return_value = (
                {
                    "answers": {
                        "claim_0": {"noul": 0.8, "confidence": 0.9},
                    }
                },
                {"input_tokens": 10, "output_tokens": 5},
            )

            result = evaluate_product_reply_with_jev(
                request="I want an action game",
                items=[{"item_id": "vg_001", "title": "Action Game", "main_category": "Action"}],
                answer="Action Game is a great choice.",
            )

            assert result["evaluation_state"] == "success"
            assert result["total_claims"] >= 0
            assert result["usage"]["input_tokens"] == 10
            mock_provider.close.assert_called_once()

    def test_evaluate_with_provider_error(self):
        """Test that provider errors return evaluation_state: provider_error."""
        with patch("package.evaluation.product_reply.evaluate_product_reply_with_jev.JevProvider") as mock_provider_class:
            mock_provider = Mock()
            mock_provider_class.return_value = mock_provider

            # Mock provider exception
            mock_provider.evaluate.side_effect = Exception("API timeout")

            result = evaluate_product_reply_with_jev(
                request="I want an action game",
                items=[{"item_id": "vg_001", "title": "Action Game", "main_category": "Action"}],
                answer="Action Game is a great choice.",
            )

            assert result["evaluation_state"] == "provider_error"
            assert result["communication"] is None
            assert result["summary"].startswith("Evaluation failed:")
            assert result["usage"]["input_tokens"] == 0
            mock_provider.close.assert_called_once()

    def test_realistic_answer_produces_claims(self):
        """Test that a realistic answer produces actual claims for faithfulness evaluation."""
        with patch("package.evaluation.product_reply.evaluate_product_reply_with_jev.JevProvider") as mock_provider_class:
            mock_provider = Mock()
            mock_provider_class.return_value = mock_provider

            # Mock faithfulness evaluation
            mock_provider.evaluate.return_value = (
                {
                    "answers": {
                        "claim_0": {"noul": 0.8, "confidence": 0.9},
                    }
                },
                {"input_tokens": 10, "output_tokens": 5},
            )

            # Use a realistic answer format (now used by grounding_benchmark.py)
            result = evaluate_product_reply_with_jev(
                request="I want an action game",
                items=[{"item_id": "vg_001", "title": "Action Game", "main_category": "Action", "price": 30.0}],
                answer="Action Game is a good choice. It belongs to the Action category. The price is $30.0.",
            )

            # Realistic answer should produce claims (not filtered as generic)
            assert result["total_claims"] > 0
            assert result["evaluation_state"] == "success"
