"""Phase 1 regression tests: grounding benchmark must not fake scores on judge failure.

Covers package/evaluation/component/benchmarks/grounding_benchmark.py:
- provider_error -> run_component raises (case FAIL), no rule-based score fallback
- partial judge errors -> judge_error_count metric, not inflated unsupported
- evidence_kind label marks the synthetic answer
- label_agreement compares Jev-derived metrics against dataset expected labels
- empty evidence -> case FAIL (nothing to ground)
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from package.evaluation.component.benchmarks.grounding_benchmark import GroundingBenchmark


def _config():
    return {"use_jev": True}


def _case_input(evidence=None, request="I want an action game"):
    return {
        "user_request": request,
        "evidence": evidence
        if evidence is not None
        else [{"item_id": "vg_001", "title": "Action Game", "main_category": "Action", "price": 30.0}],
    }


def _patched_judge_config(monkeypatch, api_key="fake_key"):
    import importlib

    mod = importlib.import_module(
        "package.evaluation.product_reply.evaluate_product_reply_with_jev"
    )
    monkeypatch.setattr(
        mod,
        "load_config",
        lambda *a, **k: {
            "api_key": api_key,
            "model": "jev-latest",
            "base_url": "https://fake.jev",
            "timeout_seconds": 5.0,
            "enable_long_context": False,
            "evaluation": {
                "faithfulness": {"support_threshold": 0.7, "instructions": "supported?"},
                "communication": {
                    "criteria": {"relevance": {"instructions": "rel?", "rubric": ["bad", "good"]}}
                },
            },
        },
    )


def _resp(answers):
    r = Mock()
    r.status_code = 200
    r.json.return_value = {"answers": answers, "usage": {"input_tokens": 1, "output_tokens": 1}}
    return r


def test_provider_error_fails_case_not_fake_score(monkeypatch):
    """Missing TYPESAFE_API_KEY -> evaluate returns provider_error -> case must FAIL."""
    _patched_judge_config(monkeypatch, api_key="")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    bench = GroundingBenchmark(config=_config())
    with pytest.raises(Exception, match="(?i)jev|provider|evaluation"):
        bench.run_component(_case_input())


def test_partial_judge_error_counted_separately(monkeypatch):
    """Faithfulness batch fails but communication succeeds -> judge_error metric, run ok."""
    _patched_judge_config(monkeypatch)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

    with patch("httpx.Client") as cls:
        client = Mock()
        cls.return_value = client
        client.post.side_effect = [
            Exception("jev down"),
            _resp({"relevance": {"score": 3}}),
        ]
        bench = GroundingBenchmark(config=_config())
        out = bench.run_component(_case_input())

    assert out["evidence_kind"] == "real_inference_output"  # Phase 4.3: real compose_answer output
    jev_result = out["jev_result"]
    assert jev_result["evaluation_state"] == "partial_error"
    assert jev_result["judge_error_count"] == 1

    metrics = bench.score_component(out, {})
    assert metrics["judge_error_count"] == 1
    # unsupported_count must equal the number of verdict=="unsupported" claims —
    # judge_error claims are excluded from both supported and unsupported counts.
    n_unsupported = sum(1 for c in jev_result["claims"] if c["verdict"] == "unsupported")
    assert metrics["unsupported_count"] == n_unsupported
    assert metrics["hallucination_rate"] == pytest.approx(
        n_unsupported / max(n_unsupported + jev_result["supported_count"], 1) if (n_unsupported + jev_result["supported_count"]) else 0.0
    )


def _actual_output(supported=1, unsupported=0, judge_errors=0):
    return {
        "jev_result": {
            "supported_count": supported,
            "unsupported_count": unsupported,
            "judge_error_count": judge_errors,
            "evaluation_state": "success" if not judge_errors else "partial_error",
        },
        "user_request": "cheap games",
    }


def test_label_agreement_full_match():
    """Expected labels matching the Jev result -> label_agreement = 1.0."""
    bench = GroundingBenchmark(config=_config())
    expected = {"claims_supported": 1, "grounding_rate": 1.0, "hallucination_rate": 0.0}
    metrics = bench.score_component(_actual_output(), expected)
    assert metrics["label_agreement"] == 1.0


def test_label_agreement_partial_and_zero():
    """A wrong expected label must be caught: agreement < 1, and 0 when all wrong."""
    bench = GroundingBenchmark(config=_config())
    # Jev says supported; expected disagrees on 2 of the 3 asserted keys
    expected = {"claims_supported": 1, "grounding_rate": 1.0, "hallucination_rate": 1.0}
    metrics = bench.score_component(_actual_output(), expected)
    assert metrics["label_agreement"] == pytest.approx(2 / 3)
    all_wrong = {"claims_supported": 0, "grounding_rate": 0.0, "hallucination_rate": 1.0}
    assert bench.score_component(_actual_output(), all_wrong)["label_agreement"] == 0.0


def test_label_agreement_absent_without_expected_keys():
    """Cases with no assertable expected keys must NOT get a free label_agreement."""
    bench = GroundingBenchmark(config=_config())
    assert "label_agreement" not in bench.score_component(_actual_output(), {})
    assert "label_agreement" not in bench.score_component(_actual_output(), {"unrelated": 1})
    # prompt_injection_detected was removed: it measured the request text, not the system
    assert "prompt_injection_detected" not in bench.score_component(_actual_output(), {})


def test_empty_evidence_fails_case():
    """No evidence -> nothing to ground -> honest case failure, not a score."""
    bench = GroundingBenchmark(config=_config())
    with pytest.raises(Exception):
        bench.run_component(_case_input(evidence=[]))
