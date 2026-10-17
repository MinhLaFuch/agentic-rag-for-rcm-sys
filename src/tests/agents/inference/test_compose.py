"""compose_answer: status routing, LLM path with grounding + retry, template fallback, usage, modes."""

import json

import pytest

from package.agents import PlanExecutor
from package.agents import extract_recommendations
from package.inference import (
    Answer,
    compose_answer,
    compose_template,
    outcome_from_plan_results,
    outcome_from_type1,
)
from package.inference._helper import check_grounding
from package.tools import QueryTool
from tests.agents.test_plan_executor import plan
from tests.agents.inference.helpers import FailingLLM, ScriptedLLM, good_reply, item, outcome, reply
from tests.tools_helpers import VG_A, VG_B

A, B, C = "Video_Games::a", "Video_Games::b", "Electronics::c"
FAKE = "Video_Games::made_up"
KW = dict(mode="llm", max_tokens=256, temperature=0.0, llm_retries=1, check_numbers=True, price_tolerance=0.5)


def three():
    return [item(A, "Alpha", 10.0, 4.5), item(B, "Beta", None, 4.0), item(C, "Gamma", 25.5, None)]


# ---------------------------------------------------------------- happy path, end to end with a real PlanExecutor

def test_planner_items_get_a_grounded_llm_answer_and_nothing_else_changes(corpus):
    request = f"tell me about {VG_A} and {VG_B}"
    planner_llm = ScriptedLLM(plan({"tool": "QueryTool", "args": {"item_ids": [VG_A, VG_B]}}))
    executor = PlanExecutor(planner_llm, [QueryTool(corpus)])
    results = executor.run(request)
    usage_before, plan_before = dict(executor.last_usage), list(executor.last_plan)
    agent_ids = extract_recommendations(results, 10)

    out = outcome_from_plan_results(request, results, question=executor.last_question, max_items=10)
    inference_llm = ScriptedLLM(good_reply(out.items))
    answer = compose_answer(out, inference_llm, **KW)

    assert isinstance(answer, Answer)
    assert answer.status == "ok" and answer.composer == "llm" and answer.grounded and answer.fallback_reason is None
    assert [i["item_id"] for i in answer.items] == agent_ids == [VG_A, VG_B]  # same items, same order
    assert VG_A in answer.text and VG_B in answer.text
    assert len(inference_llm.calls) == 1
    assert answer.usage == {"attempts": 1, "prompt_tokens": 10, "completion_tokens": 5, "latency_seconds": pytest.approx(0.1)}
    assert executor.last_usage == usage_before and executor.last_plan == plan_before  # planner state untouched
    assert len(planner_llm.calls) == 1  # Inference did not call the planner's LLM


def test_llm_request_carries_the_data_and_json_mode():
    llm = ScriptedLLM(good_reply(three()))
    compose_answer(outcome(three(), request_text="giá dưới 30 đô"), llm, **KW)
    system, user = llm.calls[0][0].content, llm.calls[0][-1].content
    assert "mentioned_item_ids" in system and "never" in system.lower()
    payload = json.loads(user[user.index("{"):])
    assert payload["request"] == "giá dưới 30 đô" and [i["item_id"] for i in payload["items"]] == [A, B, C]


# ---------------------------------------------------------------- grounding, retry, fallback

def test_foreign_id_is_retried_and_the_retry_carries_the_reason():
    items = three()
    bad = reply(f"1. Alpha ({A})\n2. Beta ({B})\n3. Gamma ({C})\n4. Ghost ({FAKE})", [A, B, C, FAKE])
    llm = ScriptedLLM(bad, good_reply(items))
    answer = compose_answer(outcome(items), llm, **KW)
    assert answer.composer == "llm" and answer.grounded and FAKE not in answer.text
    assert answer.usage["attempts"] == 2 and answer.usage["prompt_tokens"] == 20 and answer.usage["completion_tokens"] == 10
    retry = llm.calls[1]
    assert retry[-2].role == "assistant" and retry[-2].content == bad
    assert "rejected" in retry[-1].content and FAKE in retry[-1].content


def test_retries_exhausted_falls_back_to_the_template_without_the_fake_id():
    items = three()
    bad = reply(f"1. Alpha ({A})\n2. Beta ({B})\n3. Gamma ({C})\n4. Ghost ({FAKE})", [A, B, C, FAKE])
    llm = ScriptedLLM(bad, bad)
    answer = compose_answer(outcome(items), llm, **KW)
    assert answer.status == "ok" and answer.composer == "template" and answer.grounded
    assert answer.fallback_reason and answer.fallback_reason.startswith("ungrounded") and FAKE in answer.fallback_reason
    assert FAKE not in answer.text and all(i["item_id"] in answer.text for i in items)
    assert [i["item_id"] for i in answer.items] == [A, B, C]
    assert answer.usage["attempts"] == 2 and answer.usage["completion_tokens"] == 10  # cost of the failed tries is kept


def test_no_retry_when_disabled():
    llm = ScriptedLLM(reply(f"x ({FAKE})", [FAKE]))
    answer = compose_answer(outcome(three()), llm, **{**KW, "llm_retries": 0})
    assert len(llm.calls) == 1 and answer.composer == "template" and answer.usage["attempts"] == 1


@pytest.mark.parametrize("raw", ["not json at all", "[1, 2]", json.dumps({"answer": 5, "mentioned_item_ids": []}),
                                 json.dumps({"answer": "", "mentioned_item_ids": []}), json.dumps({"answer": "hello"}),
                                 json.dumps({"answer": "hello", "mentioned_item_ids": "nope"})])
def test_unusable_json_falls_back_without_raising(raw):
    answer = compose_answer(outcome(three()), ScriptedLLM(raw), **{**KW, "llm_retries": 0})
    assert answer.composer == "template" and answer.fallback_reason.startswith("invalid_json") and answer.grounded


def test_json_in_a_code_fence_is_accepted():
    items = three()
    answer = compose_answer(outcome(items), ScriptedLLM("```json\n" + good_reply(items) + "\n```"), **KW)
    assert answer.composer == "llm" and answer.grounded


def test_provider_error_falls_back_and_never_raises():
    llm = FailingLLM()
    answer = compose_answer(outcome(three()), llm, **KW)
    assert answer.status == "ok" and answer.composer == "template" and answer.grounded
    assert answer.fallback_reason.startswith("provider_error") and len(answer.fallback_reason) <= 400
    assert len(llm.calls) == 1  # a provider error is not retried like a bad reply
    assert answer.usage == {"attempts": 1, "prompt_tokens": 0, "completion_tokens": 0, "latency_seconds": 0.0}
    assert [i["item_id"] for i in answer.items] == [A, B, C]


def test_dropping_or_reordering_items_is_not_grounded():
    items = three()
    dropped = reply(f"1. Alpha ({A})\n2. Beta ({B})", [A, B])
    reordered = reply(f"1. Beta ({B})\n2. Alpha ({A})\n3. Gamma ({C})", [B, A, C])
    for bad in (dropped, reordered):
        answer = compose_answer(outcome(items), ScriptedLLM(bad, bad), **KW)
        assert answer.composer == "template" and answer.fallback_reason.startswith("ungrounded")
    assert [i["item_id"] for i in answer.items] == [A, B, C]


def test_mentioned_ids_must_match_the_ids_in_the_text():
    items = three()
    text = "\n".join(it["item_id"] for it in items)  # ids present in the text, but the declared list is incomplete
    answer = compose_answer(outcome(items), ScriptedLLM(reply(text, [A]), reply(text, [A])), **KW)
    assert answer.composer == "template"


# ---------------------------------------------------------------- numbers (check_numbers / price_tolerance)

def test_a_price_not_in_the_data_is_rejected_but_the_request_budget_is_fine():
    items = [item(A, "Alpha", 10.0, 4.5)]
    wrong = reply(f"Alpha ({A}) costs $99.00", [A])
    answer = compose_answer(outcome(items), ScriptedLLM(wrong), **{**KW, "llm_retries": 0})
    assert answer.composer == "template" and "99" in answer.fallback_reason
    ok = reply(f"Alpha ({A}) is $10.00, under your $30 budget", [A])
    answer = compose_answer(outcome(items, request_text="dưới 30 đô"), ScriptedLLM(ok), **KW)
    assert answer.composer == "llm"


def test_price_tolerance_and_the_switch_are_configurable():
    items = [item(A, "Alpha", 19.99, 4.5)]
    rounded = reply(f"Alpha ({A}) about $20", [A])
    assert compose_answer(outcome(items), ScriptedLLM(rounded), **KW).composer == "llm"  # 0.01 away, inside 0.5
    strict = compose_answer(outcome(items), ScriptedLLM(rounded), **{**KW, "price_tolerance": 0.0, "llm_retries": 0})
    assert strict.composer == "template"
    off = compose_answer(outcome(items), ScriptedLLM(reply(f"Alpha ({A}) $77", [A])), **{**KW, "check_numbers": False})
    assert off.composer == "llm"


def test_a_rating_not_in_the_data_is_rejected():
    items = [item(A, "Alpha", 10.0, 4.5)]
    answer = compose_answer(outcome(items), ScriptedLLM(reply(f"Alpha ({A}) rated 3.2/5", [A])), **{**KW, "llm_retries": 0})
    assert answer.composer == "template" and "3.2" in answer.fallback_reason
    assert compose_answer(outcome(items), ScriptedLLM(reply(f"Alpha ({A}) rated 4.5/5", [A])), **KW).composer == "llm"


def test_a_bare_asin_that_is_not_in_the_list_is_rejected():
    items = [item("Video_Games::B0ABCDEFGH", "Alpha")]
    text = "Alpha (Video_Games::B0ABCDEFGH), see also B0ZZZZZZZZ"
    answer = compose_answer(outcome(items), ScriptedLLM(reply(text, ["Video_Games::B0ABCDEFGH"])), **{**KW, "llm_retries": 0})
    assert answer.composer == "template" and "B0ZZZZZZZZ" in answer.fallback_reason


def test_check_grounding_matches_whole_ids_not_prefixes():
    items = [item("Video_Games::B01234567X", "Alpha")]
    problem = check_grounding("Alpha (Video_Games::B01234)", ["Video_Games::B01234"], outcome(items), check_numbers=True, price_tolerance=0.5)
    assert problem and "Video_Games::B01234" in problem
    assert check_grounding("Alpha (Video_Games::B01234567X).", ["Video_Games::B01234567X"], outcome(items),
                           check_numbers=True, price_tolerance=0.5) is None  # trailing punctuation is not part of the id


# ---------------------------------------------------------------- statuses that never call the LLM

def test_ask_user_returns_the_question_and_never_calls_the_llm():
    llm = ScriptedLLM()
    out = outcome([], question="Bạn muốn mua loại sản phẩm nào?", n_steps=0)
    answer = compose_answer(out, llm, **KW)
    assert answer.status == "ask_user" and answer.text == "Bạn muốn mua loại sản phẩm nào?" and answer.items == []
    assert llm.calls == [] and answer.usage["attempts"] == 0 and answer.fallback_reason is None


def test_no_result_is_announced_without_the_llm():
    llm = ScriptedLLM()
    answer = compose_answer(outcome([], n_steps=3), llm, **KW)
    assert answer.status == "no_result" and answer.text.strip() and answer.items == [] and llm.calls == []
    empty_plan = compose_answer(outcome([], n_steps=0), llm, **KW)
    assert empty_plan.status == "no_result" and llm.calls == []


def test_tool_error_hides_internal_errors():
    llm = ScriptedLLM()
    secret = "Traceback (most recent call last): KeyError SECRET_TABLE " + "z" * 2000
    out = outcome([], errors=[{"tool": "ItemCFTool", "error": secret[:300]}])
    answer = compose_answer(out, llm, **KW)
    assert answer.status == "tool_error" and answer.items == [] and llm.calls == []
    assert "SECRET_TABLE" not in answer.text and "Traceback" not in answer.text and "ItemCFTool" not in answer.text
    assert len(answer.text) < 400 and answer.reason.startswith("tool_error") and "ItemCFTool" in answer.reason and len(answer.reason) <= 400


def test_invented_ids_are_a_tool_error_even_when_other_steps_returned_items():
    llm = ScriptedLLM()
    out = outcome(three(), invented_ids=[FAKE], errors=[{"tool": "QueryTool", "error": "id(s) not found"}])
    answer = compose_answer(out, llm, **KW)
    assert answer.status == "tool_error" and answer.items == [] and llm.calls == [] and FAKE not in answer.text
    assert FAKE in answer.reason


def test_plan_error_is_a_tool_error():
    out = outcome([], errors=[{"tool": "planner", "error": "ValueError: bad json"}], n_steps=0)
    assert compose_answer(out, ScriptedLLM(), **KW).status == "tool_error"


def test_failed_step_with_no_items_is_a_tool_error():
    out = outcome([], errors=[{"tool": "RecoModelTool", "error": "no scorer"}])
    assert compose_answer(out, ScriptedLLM(), **KW).status == "tool_error"


def test_question_wins_only_when_the_plan_has_no_steps():
    asked_and_ran = outcome(three(), question="Which game?", n_steps=2)
    answer = compose_answer(asked_and_ran, ScriptedLLM(good_reply(three())), **KW)
    assert answer.status == "ok" and "question ignored" in answer.reason
    ran_empty = compose_answer(outcome([], question="Which game?", n_steps=2), ScriptedLLM(), **KW)
    assert ran_empty.status == "no_result" and "question ignored" in ran_empty.reason


def test_a_failed_auxiliary_step_still_gives_an_ok_partial_answer():
    out = outcome(three(), errors=[{"tool": "QueryTool", "error": "timeout"}])
    answer = compose_answer(out, ScriptedLLM(good_reply(three())), **KW)
    assert answer.status == "ok" and answer.reason.startswith("partial") and "QueryTool" in answer.reason
    template = compose_template(out)
    assert template.status == "ok" and template.text != compose_template(outcome(three())).text  # neutral wording


# ---------------------------------------------------------------- modes

def test_template_mode_never_calls_the_llm_and_is_not_a_fallback():
    llm = ScriptedLLM()
    answer = compose_answer(outcome(three()), llm, **{**KW, "mode": "template"})
    assert llm.calls == [] and answer.composer == "template" and answer.fallback_reason is None and answer.grounded
    assert answer.usage["attempts"] == 0


def test_llm_mode_without_a_provider_is_a_fallback():
    answer = compose_answer(outcome(three()), None, **KW)
    assert answer.composer == "template" and answer.fallback_reason == "no_llm"


def test_defaults_come_from_inference_yaml(monkeypatch):
    # no keyword config: mode comes from inference.yaml (llm), so a scripted LLM is used
    llm = ScriptedLLM(good_reply(three()))
    assert compose_answer(outcome(three()), llm).composer == "llm"


def test_max_items_cut_is_applied_by_the_adapter_and_the_answer_shows_only_those():
    results = [{"tool": "RecoModelTool", "ok": True, "error": None, "invented_ids": [],
                "data": {"ranked": [{"rank": n, "item_id": f"Video_Games::i{n}", "score": 1.0, "domain": "Video_Games"} for n in range(1, 6)]}}]
    out = outcome_from_plan_results("req", results, question=None, max_items=2)
    answer = compose_template(out)
    assert [i["item_id"] for i in answer.items] == ["Video_Games::i1", "Video_Games::i2"]
    assert "Video_Games::i3" not in answer.text


# ---------------------------------------------------------------- template content

def test_template_is_deterministic_grounded_and_marks_missing_metadata():
    items = [item(A, "Alpha", 10.0, 4.5), item(B, None, None, None, store=None, rating_number=None)]
    first, second = compose_template(outcome(items)), compose_template(outcome(items))
    assert first.text == second.text and first.composer == "template" and first.fallback_reason is None
    assert check_grounding(first.text, [i["item_id"] for i in items], outcome(items), check_numbers=True, price_tolerance=0.0) is None
    lines = first.text.splitlines()
    assert any(A in l and "Alpha" in l for l in lines) and "$10.00" in first.text and "4.5/5" in first.text
    b_block = first.text[first.text.index(B):]
    assert "$" not in b_block and "chỉ có mã" in b_block  # no invented price; says only the id is known


def test_template_cuts_very_long_titles():
    long_title = "W" * 500
    text = compose_template(outcome([item(A, long_title)])).text
    assert long_title not in text and "W" * 50 in text


def test_type1_outcome_goes_through_the_same_composer():
    out = outcome_from_type1("similar to X", {"ok": True, "cold_start": False, "items": [
        {"rank": 1, "item_id": A, "score": 0.5, "domain": "Video_Games", "title": "Alpha", "price": 10.0}]}, max_items=10)
    answer = compose_answer(out, ScriptedLLM(good_reply(out.items)), **KW)
    assert answer.status == "ok" and answer.composer == "llm" and [i["item_id"] for i in answer.items] == [A]
    failed = compose_answer(outcome_from_type1("x", {"ok": False, "stage": "retrieve", "error": "boom"}), ScriptedLLM(), **KW)
    assert failed.status == "tool_error" and "retrieve" in failed.reason
    cold = compose_answer(outcome_from_type1("x", {"ok": True, "items": [], "cold_start": True}), ScriptedLLM(), **KW)
    assert cold.status == "no_result"


def test_answer_serializes_to_plain_json():
    answer = compose_template(outcome(three()))
    assert json.loads(json.dumps(answer.to_dict(), ensure_ascii=False))["status"] == "ok"
