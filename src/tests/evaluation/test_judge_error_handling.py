"""Phase 1 regression tests: judge errors must not be scored as unsupported claims.

Covers package/evaluation/product_reply/evaluate_product_reply_with_jev.py:
- Jev batch failure -> verdict "judge_error", NOT "unsupported"
- unsupported_count / supported_count / judge_error_count are separate
- evaluation_state "partial_error" when only some calls fail
- JevProvider init failure (missing key) -> provider_error dict, never raises
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from package.evaluation.product_reply.evaluate_product_reply_with_jev import (
    evaluate_product_reply_with_jev,
)


def _judge_config(api_key: str = "fake_key") -> dict:
    return {
        "provider": "jev",
        "api_key": api_key,
        "model": "jev-latest",
        "base_url": "https://fake.jev",
        "timeout_seconds": 5.0,
        "enable_long_context": False,
        "evaluation": {
            "faithfulness": {
                "support_threshold": 0.7,
                "instructions": "Is the claim supported by item fields?",
            },
            "communication": {
                "criteria": {
                    "relevance": {"instructions": "relevant?", "rubric": ["bad", "good"]},
                }
            },
        },
    }


_ITEMS = [
    {
        "item_id": "vg_001",
        "domain": "Video_Games",
        "title": "Action Game",
        "store": "Amazon",
        "price": 30.0,
        "average_rating": 4.5,
        "rating_number": 100,
        "main_category": "Action",
    }
]

# Sentence overlaps the item title on >=2 words -> claim gets item_id vg_001
_ANSWER = "Action Game costs $30 and is great."


def _patched_config(monkeypatch, api_key: str = "fake_key"):
    import importlib

    mod = importlib.import_module(
        "package.evaluation.product_reply.evaluate_product_reply_with_jev"
    )
    monkeypatch.setattr(mod, "load_config", lambda *a, **k: _judge_config(api_key))


def _ok_response():
    resp = Mock()
    resp.status_code = 200
    resp.json.return_value = {
        "answers": {"claim_0": {"noul": 0.9, "confidence": 0.9}},
        "usage": {"input_tokens": 5, "output_tokens": 2},
    }
    return resp


def _comm_response():
    resp = Mock()
    resp.status_code = 200
    resp.json.return_value = {
        "answers": {"relevance": {"score": 3}},
        "usage": {"input_tokens": 5, "output_tokens": 2},
    }
    return resp


def test_judge_batch_error_marks_judge_error_not_unsupported(monkeypatch):
    """A Jev API failure on the faithfulness batch must NOT count as unsupported."""
    _patched_config(monkeypatch)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    with patch("httpx.Client") as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        # call 1 = faithfulness batch (fails), call 2 = communication (succeeds)
        mock_client.post.side_effect = [Exception("jev api down"), _comm_response()]

        result = evaluate_product_reply_with_jev(
            request="action games", items=_ITEMS, answer=_ANSWER
        )

    assert result["evaluation_state"] == "partial_error"
    assert result["judge_error_count"] == 1
    assert result["unsupported_count"] == 0
    assert result["supported_count"] == 0
    errored = [c for c in result["claims"] if c["verdict"] == "judge_error"]
    assert len(errored) == 1
    assert "Jev error" in errored[0]["why"]


def test_missing_api_key_returns_provider_error_dict(monkeypatch):
    """JevProvider init failure must return a dict, not raise (contract: always dict)."""
    _patched_config(monkeypatch, api_key="")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    result = evaluate_product_reply_with_jev(
        request="action games", items=_ITEMS, answer=_ANSWER
    )

    assert isinstance(result, dict)
    assert result["evaluation_state"] == "provider_error"
    assert result["total_claims"] == 0


def test_success_path_unchanged(monkeypatch):
    """Healthy Jev path still reports success with supported claim."""
    _patched_config(monkeypatch)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    with patch("httpx.Client") as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.post.side_effect = [_ok_response(), _comm_response()]

        result = evaluate_product_reply_with_jev(
            request="action games", items=_ITEMS, answer=_ANSWER
        )

    assert result["evaluation_state"] == "success"
    assert result["judge_error_count"] == 0
    assert result["unsupported_count"] == 0
    assert result["supported_count"] >= 1
