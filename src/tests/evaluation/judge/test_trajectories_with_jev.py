"""Post-hoc Jev pass over trajectories: eligibility, context, caps, credentials."""

import importlib

import pytest

import package.evaluation.judge as judge_pkg
from package.evaluation import AgentRequest
from package.evaluation.judge import (
    evaluate_trajectories_with_jev,
    jev_credentials_configured,
)
from scripts.evaluation.run_agent_eval import run_optional_jev
from tests.tools_helpers import VG_A, VG_B

# The package __init__ re-exports the functions under the same names as the
# modules, so string-path monkeypatching would hit the function, not the module.
_eval_mod = importlib.import_module("package.evaluation.judge.evaluate_trajectories_with_jev")


def _request(rid="r0"):
    return AgentRequest(request_id=rid, kind="similar", segment="warm", text="gợi ý tương tự",
                        targets=[1], oracle=False)


def _traj(rid="r0", **over):
    traj = {
        "request_id": rid, "agent": "planner", "answer_status": "ok",
        "answer": "VG_A is a great pick at $19.99.", "recommended": [VG_A, VG_B],
    }
    traj.update(over)
    return traj


_FAKE_RESULT = {
    "claims": [{"text": "c", "item_id": VG_A, "verdict": "supported", "why": "w"}],
    "unsupported_count": 0, "supported_count": 1, "judge_error_count": 0,
    "total_claims": 1, "lists_all_items_in_order": True,
    "communication": {"relevance": 5}, "summary": "ok",
    "usage": {"input_tokens": 10, "output_tokens": 5},
    "evaluation_state": "success",
}


@pytest.fixture
def fake_jev(monkeypatch):
    calls = []

    def fake(request, items, answer):
        calls.append({"request": request, "items": items, "answer": answer})
        return dict(_FAKE_RESULT)

    monkeypatch.setattr(_eval_mod, "evaluate_product_reply_with_jev", fake)
    return calls


def test_eligibility_and_context(corpus, fake_jev):
    requests = {"r0": _request(), "r1": _request("r1")}
    trajs = [
        _traj("r0"),                                                    # eligible
        _traj("r1", answer_status="no_result"),                          # not answered -> skip
        _traj("r2", answer=None),                                        # empty answer -> skip
        _traj("r3", recommended=[]),                                     # nothing recommended -> skip
        _traj("rX"),                                                     # unknown request -> skip
        {"request_id": "r1", "agent": "baseline", "answer_status": "ok",
         "answer": "x", "recommended": [VG_A]},                          # baseline agent still judged
    ]
    rows = evaluate_trajectories_with_jev(trajs, requests, corpus)
    assert [r["request_id"] for r in rows] == ["r0", "r1"]
    row = rows[0]
    assert row["agent"] == "planner" and row["kind"] == "similar"
    assert row["segment"] == "warm" and row["oracle"] is False
    assert row["evaluation_state"] == "success" and row["supported_count"] == 1
    # items carry corpus metadata, deduplicated, in recommended order
    assert [i["item_id"] for i in fake_jev[0]["items"]] == [VG_A, VG_B]
    assert fake_jev[0]["items"][0]["title"] == "Super Video Game"


def test_max_requests_caps_deterministically(corpus, fake_jev):
    requests = {f"r{i}": _request(f"r{i}") for i in range(3)}
    trajs = [_traj(f"r{i}") for i in range(3)]
    rows = evaluate_trajectories_with_jev(trajs, requests, corpus, max_requests=2)
    assert [r["request_id"] for r in rows] == ["r0", "r1"]
    assert len(fake_jev) == 2


def test_missing_item_metadata_skips_case(corpus, fake_jev):
    requests = {"r0": _request()}
    trajs = [_traj("r0", recommended=["Ghost::nope"])]
    assert evaluate_trajectories_with_jev(trajs, requests, corpus) == []
    assert fake_jev == []


def test_run_optional_jev_disabled_and_credentials(tmp_path, monkeypatch):
    # disabled -> (None, [])
    assert run_optional_jev({}, [], {}, None, tmp_path) == (None, [])
    # enabled without credentials -> skipped_no_credentials, no rows
    # run_optional_jev imports the symbol lazily from the package — patch there
    monkeypatch.setattr(judge_pkg, "jev_credentials_configured", lambda: False)
    info, rows = run_optional_jev({"jev": {"enabled": True}}, [], {}, None, tmp_path)
    assert info["status"] == "skipped_no_credentials" and rows == []
    assert info["output_path"].endswith("jev_eval.jsonl")


def test_jev_credentials_configured_env(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    assert jev_credentials_configured() is True
