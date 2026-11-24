"""Distill spec extraction + PlanExecutor pre-planner injection."""

import json

import pytest

pytestmark = pytest.mark.integration

from package.agents import PlanExecutor
from package.agents.distill import extract_spec, make_spec_extractor
from package.tools import FilterTool
from tests.agents.fakes.scripted_llm import ScriptedLLM


def _spec_json(**over):
    base = {
        "kind": "cold_text",
        "category_coarse": None,
        "category_leaf": "Baby Floats",
        "price_max": None,
        "min_rating": None,
        "exclusions": {"item_ids": [], "category_labels": []},
        "seed_item_id": None,
        "attributes": None,
        "language": "vi",
    }
    base.update(over)
    return json.dumps(base)


def test_extract_spec_happy_path_flattens_slots():
    llm = ScriptedLLM(_spec_json())
    spec, usage = extract_spec(llm, "Tìm 10 sản phẩm nhóm Baby Floats")
    assert spec["kind"] == "cold_text"
    assert spec["category_leaf"] == "Baby Floats"  # flattened, not {"value": ...}
    assert "category_coarse" not in spec          # nulls dropped
    assert usage["prompt_tokens"] == 10 and usage["error"] is None


def test_extract_spec_invalid_json_returns_none():
    llm = ScriptedLLM("no json here")
    spec, usage = extract_spec(llm, "hello")
    assert spec is None and usage["error"]


def test_extract_spec_validation_failure_returns_none():
    # kind=similar requires seed_item_id -> Spec validation must reject
    llm = ScriptedLLM(_spec_json(kind="similar", category_leaf=None))
    spec, usage = extract_spec(llm, "tìm đồ tương tự")
    assert spec is None and "validation" in (usage["error"] or "")


def test_extract_spec_provider_error_is_contained():
    from package.api import LLMProviderError
    llm = ScriptedLLM(LLMProviderError("boom"))
    spec, usage = extract_spec(llm, "x")
    assert spec is None and usage["error"]


def test_extract_spec_normalizes_category_case(corpus):
    # fixture corpus has known categories; pick one and send wrong case
    cats = corpus.categories()
    if not cats:
        pytest.skip("empty corpus fixture")
    canon = cats[0]
    wrong = canon.swapcase()
    if wrong == canon:
        pytest.skip("category has no case to flip")
    llm = ScriptedLLM(_spec_json(category_leaf=wrong))
    spec, _ = extract_spec(llm, "x", corpus=corpus)
    assert spec["category_leaf"] == canon


def _plan(step):
    return json.dumps({"steps": [step], "ask_user": None})


def test_executor_injects_spec_block_and_records_distill(corpus):
    spec_llm = ScriptedLLM(_spec_json())
    plan_llm = ScriptedLLM(_plan({"tool": "FilterTool", "args": {"limit": 2}}))

    # extractor shares the same provider interface; give it its own scripted llm
    extractor = make_spec_extractor(spec_llm, corpus=corpus)
    executor = PlanExecutor(plan_llm, [FilterTool(corpus)], spec_extractor=extractor)
    executor.run("Tìm 10 sản phẩm nhóm Baby Floats")

    system_msg = plan_llm.calls[0]["messages"][0].content
    assert "Distilled request spec" in system_msg
    assert "Baby Floats" in system_msg
    assert executor.last_distill is not None
    assert executor.last_distill["spec"]["kind"] == "cold_text"
    # extractor tokens are NOT folded into planner usage
    assert executor.last_usage["prompt_tokens"] == 10


def test_executor_without_extractor_unchanged(corpus):
    plan_llm = ScriptedLLM(_plan({"tool": "FilterTool", "args": {"limit": 1}}))
    executor = PlanExecutor(plan_llm, [FilterTool(corpus)])
    executor.run("list items")
    assert "Distilled request spec" not in plan_llm.calls[0]["messages"][0].content
    assert executor.last_distill is None


def test_extractor_failure_never_sinks_planning(corpus):
    def boom(text):
        raise RuntimeError("extractor exploded")
    plan_llm = ScriptedLLM(_plan({"tool": "FilterTool", "args": {"limit": 1}}))
    executor = PlanExecutor(plan_llm, [FilterTool(corpus)], spec_extractor=boom)
    results = executor.run("list items")
    assert results and results[0]["ok"]
    assert executor.last_distill["spec"] is None
    assert "exploded" in executor.last_distill["usage"]["error"]


def test_extract_spec_flags_unverified_category(corpus):
    cats = corpus.categories()
    if not cats:
        pytest.skip("empty corpus fixture")
    real = cats[0]
    llm = ScriptedLLM(_spec_json(category_leaf="NonExistentCategory999"))
    spec, _ = extract_spec(llm, "x", corpus=corpus)
    assert spec["category_unverified"] == ["NonExistentCategory999"]

    llm2 = ScriptedLLM(_spec_json(category_leaf=real))
    spec2, _ = extract_spec(llm2, "x", corpus=corpus)
    assert "category_unverified" not in spec2
