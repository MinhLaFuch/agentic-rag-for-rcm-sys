"""Inference in the evaluation path: trajectory fields, scoring columns, summary, resume, and one end-to-end scenario."""

import json
import sys

import pytest

from package.agents import PlanExecutor
from package.evaluation.agent import INFERENCE_AGENTS, AgentRequest, score_trajectory, summarize
from package.evaluation.agent._schema import ANSWER_STATUSES
from package.inference import compose_answer
from package.inference._schema import STATUSES
from package.tools import QueryTool
from tests.agents.test_agent_eval import ITEM2ID, _load_run_agent_eval, _step, _trajectory
from tests.agents.test_plan_executor import ScriptedLLM, plan
from tests.agents.inference.helpers import good_reply
from tests.tools_helpers import VG_A, VG_B

NEW_COLUMNS = ("answer_grounded", "answer_fallback", "inference_attempts", "inference_prompt_tokens",
               "inference_completion_tokens", "inference_latency_seconds", *(f"answer_status_{s}" for s in STATUSES))


def _request(text="t"):
    return AgentRequest(request_id="similar-warm-0", kind="similar", segment="warm", text=text, targets=[1])


def _answered(status="ok", grounded=True, fallback=None, composer="llm", **kw):
    traj = _trajectory(steps=[_step("ItemCFTool"), _step("RecoModelTool")], recommended=[VG_A, VG_B], **kw)
    traj.update(answer="text", answer_status=status, answer_grounded=grounded, answer_composer=composer, answer_fallback=fallback,
                answer_reason=None, inference_mode="llm",
                inference_usage={"attempts": 2, "prompt_tokens": 40, "completion_tokens": 12, "latency_seconds": 0.7})
    return traj


# ---------------------------------------------------------------- contract between the two packages

def test_answer_statuses_of_the_evaluation_match_the_inference_statuses():
    assert tuple(ANSWER_STATUSES) == tuple(STATUSES)  # duplicated on purpose: evaluation must not import inference (cycle)
    assert set(INFERENCE_AGENTS) == {"type1", "planner", "planner_memory"}  # baseline has no answer


# ---------------------------------------------------------------- scoring

def test_new_columns_do_not_change_any_existing_column(corpus):
    bare = _trajectory(steps=[_step("ItemCFTool"), _step("RecoModelTool")], recommended=[VG_A, VG_B])
    row_bare = score_trajectory(_request(), bare, item2id=ITEM2ID, corpus=corpus, k=2)
    row_full = score_trajectory(_request(), _answered(), item2id=ITEM2ID, corpus=corpus, k=2)
    assert {k: v for k, v in row_full.items() if k not in NEW_COLUMNS} == {k: v for k, v in row_bare.items() if k not in NEW_COLUMNS}
    assert row_full["task_success"] is True and row_full["recall@2"] == row_bare["recall@2"]


def test_old_trajectories_without_an_answer_score_with_empty_answer_columns(corpus):
    row = score_trajectory(_request(), _trajectory(steps=[_step("ItemCFTool"), _step("RecoModelTool")], recommended=[VG_A]),
                           item2id=ITEM2ID, corpus=corpus, k=2)
    assert all(row[c] is None for c in NEW_COLUMNS)


def test_answer_columns_for_an_ok_answer(corpus):
    row = score_trajectory(_request(), _answered(), item2id=ITEM2ID, corpus=corpus, k=2)
    assert row["answer_grounded"] is True and row["answer_fallback"] is False
    assert row["answer_status_ok"] is True and row["answer_status_ask_user"] is False
    assert (row["inference_attempts"], row["inference_prompt_tokens"], row["inference_completion_tokens"]) == (2, 40, 12)
    assert row["inference_latency_seconds"] == pytest.approx(0.7)


def test_a_fallback_is_counted_and_grounded_is_only_defined_for_ok_answers(corpus):
    fell_back = score_trajectory(_request(), _answered(fallback="ungrounded: x", composer="template"), item2id=ITEM2ID, corpus=corpus, k=2)
    assert fell_back["answer_fallback"] is True and fell_back["answer_grounded"] is True
    err = score_trajectory(_request(), _answered(status="tool_error"), item2id=ITEM2ID, corpus=corpus, k=2)
    assert err["answer_grounded"] is None and err["answer_fallback"] is None and err["answer_status_tool_error"] is True


def test_summarize_averages_the_answer_columns_and_skips_missing():
    base = {"agent": "planner", "kind": "similar", "segment": "warm"}
    rows = [
        {**base, "request_id": "a", "answer_grounded": True, "answer_fallback": False, "answer_status_ok": True, "answer_status_tool_error": False},
        {**base, "request_id": "b", "answer_grounded": True, "answer_fallback": True, "answer_status_ok": True, "answer_status_tool_error": False},
        {**base, "request_id": "c", "answer_grounded": None, "answer_fallback": None, "answer_status_ok": False, "answer_status_tool_error": True},
        {**base, "request_id": "d", "answer_grounded": None, "answer_fallback": None, "answer_status_ok": None, "answer_status_tool_error": None},
    ]
    stats = summarize(rows)["planner"]["similar"]["all"]
    assert stats["answer_grounded"] == 1.0 and stats["answer_fallback"] == 0.5
    assert stats["answer_status_ok"] == pytest.approx(2 / 3) and stats["answer_status_tool_error"] == pytest.approx(1 / 3)


def test_summary_columns_print_the_answer_metrics():
    columns = _load_run_agent_eval().SUMMARY_COLUMNS
    assert {"answer_grounded", "answer_fallback", "answer_status_ok"} <= set(columns)


# ---------------------------------------------------------------- run_planner / run_type1

def _executor(corpus, *replies):
    return PlanExecutor(ScriptedLLM(*replies), [QueryTool(corpus)], plan_retries=0, reflect_rounds=0)


def _two_items_request():
    return _request(f"tell me about {VG_A} and {VG_B}")


QUERY_PLAN = plan({"tool": "QueryTool", "args": {"item_ids": [VG_A, VG_B]}})


def test_run_planner_without_an_answerer_leaves_the_answer_fields_empty(corpus):
    traj = _load_run_agent_eval().run_planner(_executor(corpus, QUERY_PLAN), _two_items_request(), "planner", 2)
    assert traj["answer"] is None and traj["answer_status"] is None and traj["inference_usage"] == {} and traj["inference_mode"] is None


def test_run_planner_adds_the_answer_without_touching_the_recommendation_or_planner_usage(corpus):
    script = _load_run_agent_eval()
    plain = script.run_planner(_executor(corpus, QUERY_PLAN), _two_items_request(), "planner", 2)
    infer_llm = ScriptedLLM()

    def answerer(outcome):
        infer_llm.replies.append(good_reply(outcome.items))
        return compose_answer(outcome, infer_llm, mode="llm")

    with_answer = script.run_planner(_executor(corpus, QUERY_PLAN), _two_items_request(), "planner", 2, answerer=answerer, inference_mode="llm")
    for key in ("recommended", "plan", "error", "reflections", "first_attempt_ok", "ask_user"):
        assert with_answer[key] == plain[key], key
    brief = lambda t: [(s["tool"], s["ok"], s["error"]) for s in t["steps"]]  # latency differs between two runs
    assert brief(with_answer) == brief(plain)
    assert {k: v for k, v in with_answer["usage"].items() if k != "latency_seconds"} == {k: v for k, v in plain["usage"].items() if k != "latency_seconds"}
    assert with_answer["recommended"] == [VG_A, VG_B]
    assert with_answer["answer_status"] == "ok" and with_answer["answer_composer"] == "llm" and with_answer["answer_grounded"] is True
    assert with_answer["answer_fallback"] is None and VG_A in with_answer["answer"] and with_answer["inference_mode"] == "llm"
    assert with_answer["inference_usage"]["attempts"] == 1 and with_answer["usage"]["attempts"] == 1  # two separate ledgers
    json.dumps(with_answer, ensure_ascii=False)


def test_run_planner_answers_even_when_the_plan_failed_and_never_calls_the_llm_for_it(corpus):
    infer_llm = ScriptedLLM()
    traj = _load_run_agent_eval().run_planner(
        _executor(corpus, "nope"), _two_items_request(), "planner", 2,
        answerer=lambda o: compose_answer(o, infer_llm, mode="llm"), inference_mode="llm")
    assert traj["error"] and traj["answer_status"] == "tool_error" and traj["recommended"] == [] and infer_llm.calls == []
    assert "planner" not in traj["answer"]


def test_run_planner_ask_user_returns_the_question_as_the_answer(corpus):
    infer_llm = ScriptedLLM()
    traj = _load_run_agent_eval().run_planner(
        _executor(corpus, plan(ask_user="Bạn cần loại sản phẩm nào?")), _request("gợi ý sản phẩm hay"), "planner", 2,
        answerer=lambda o: compose_answer(o, infer_llm, mode="llm"), inference_mode="llm")
    assert traj["answer_status"] == "ask_user" and traj["answer"] == "Bạn cần loại sản phẩm nào?" and infer_llm.calls == []


class _FakeType1:
    def __init__(self, out):
        self.out = out

    def recommend(self, user_id, seed_items, top_k=10):
        return self.out


def test_run_type1_keeps_the_recommendation_and_adds_the_answer():
    script = _load_run_agent_eval()
    request = AgentRequest(request_id="similar-warm-0", kind="similar", segment="warm", text="similar to x", user_id="u1", seed_item_id=VG_A, targets=[1])
    out = {"ok": True, "cold_start": False, "items": [{"rank": 1, "item_id": VG_B, "score": 0.4, "domain": "Video_Games", "title": "Beta", "price": 3.0}]}
    traj = script.run_type1(_FakeType1(out), request, 2, answerer=lambda o: compose_answer(o, None, mode="template"), inference_mode="template")
    assert traj["agent"] == "type1" and traj["recommended"] == [VG_B] and traj["error"] is None and traj["usage"] == {}
    assert traj["answer_status"] == "ok" and traj["answer_composer"] == "template" and traj["answer_fallback"] is None and VG_B in traj["answer"]
    failed = script.run_type1(_FakeType1({"ok": False, "stage": "rank", "error": "boom"}), request, 2,
                              answerer=lambda o: compose_answer(o, None, mode="template"), inference_mode="template")
    assert failed["error"] == "rank: boom" and failed["recommended"] == [] and failed["answer_status"] == "tool_error"
    bare = script.run_type1(_FakeType1(out), request, 2)
    assert bare["recommended"] == [VG_B] and bare["answer"] is None


# ---------------------------------------------------------------- resume / CLI

def test_resume_keeps_old_records_and_drops_other_inference_modes():
    keep = _load_run_agent_eval().is_resumable
    text_of = {"r0": "hello"}
    rec = {"request_id": "r0", "agent": "planner", "text": "hello", "reflect_rounds": 0, "inference_mode": "llm"}
    assert keep(rec, text_of, ["planner"], 0, "llm")
    assert not keep(rec, text_of, ["planner"], 0, "template")  # LLM and template answers must not be mixed in one experiment
    old = {k: v for k, v in rec.items() if k != "inference_mode"}  # written before Inference existed: reusable, answer columns stay empty
    assert keep(old, text_of, ["planner"], 0, "llm") and keep(old, text_of, ["planner"], 0, "template")
    type1 = {"request_id": "r0", "agent": "type1", "text": "hello", "inference_mode": "llm"}
    assert keep(type1, text_of, ["type1"], 0, "llm") and not keep(type1, text_of, ["type1"], 0, "template")
    baseline = {"request_id": "r0", "agent": "baseline", "text": "hello", "inference_mode": None}
    assert keep(baseline, text_of, ["baseline"], 0, "template")  # no Inference for the baseline
    assert keep(rec, text_of, ["planner"], 0)  # the old call signature still works


def test_inference_mode_is_a_cli_flag(monkeypatch, capsys):
    script = _load_run_agent_eval()
    monkeypatch.setattr(sys, "argv", ["run_agent_eval.py", "--help"])
    with pytest.raises(SystemExit) as helped:
        script.main()
    assert helped.value.code == 0 and "--inference-mode" in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", ["run_agent_eval.py", "--inference-mode", "gpt"])
    with pytest.raises(SystemExit) as bad:
        script.main()
    assert bad.value.code == 2


# ---------------------------------------------------------------- end to end: request -> planner -> Inference -> trajectory -> score -> summary

@pytest.mark.parametrize("mode", ["llm", "template"])
def test_end_to_end_scenario(corpus, mode):
    script = _load_run_agent_eval()
    request = AgentRequest(request_id="similar-warm-0", kind="similar", segment="warm", text=f"similar to {VG_A} and {VG_B}", targets=[1])
    infer_llm = ScriptedLLM()

    def answerer(outcome):
        if mode == "llm":
            infer_llm.replies.append(good_reply(outcome.items))
        return compose_answer(outcome, infer_llm, mode=mode)

    traj = script.run_planner(_executor(corpus, QUERY_PLAN), request, "planner", 2, answerer=answerer, inference_mode=mode)
    baseline = script.empty_trajectory(request, "baseline", [])
    baseline["recommended"] = [VG_A]
    rows = [score_trajectory(request, t, item2id=ITEM2ID, corpus=corpus, k=2) for t in (traj, baseline)]
    summary = summarize(rows)

    planner = summary["planner"]["similar"]["all"]
    assert planner["task_success"] == 1.0 and planner["answer_status_ok"] == 1.0 and planner["answer_grounded"] == 1.0
    assert planner["answer_fallback"] == 0.0  # mode=template is a choice, not a fallback
    assert len(infer_llm.calls) == (1 if mode == "llm" else 0)
    assert planner["inference_attempts"] == (1 if mode == "llm" else 0)
    assert "answer_grounded" not in summary["baseline"]["similar"]["all"]  # the baseline has no Inference
    json.dumps(summary)
