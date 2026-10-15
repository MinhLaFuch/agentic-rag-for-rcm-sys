"""AgentOutcome adapters: PlanExecutor results and Type1Agent output -> one normalized outcome."""

from package.agents.evaluation.extract_recommendations import extract_recommendations
from package.inference import outcome_from_plan_results, outcome_from_type1
from package.inference._schema import ITEM_FIELDS

A, B, C = "Video_Games::a", "Video_Games::b", "Electronics::c"


def step(tool, data=None, ok=True, error=None, invented_ids=()):
    return {"tool": tool, "ok": ok, "data": data or {}, "error": error, "invented_ids": list(invented_ids), "latency_seconds": 0.0}


def ranked(*ids):
    return step("RecoModelTool", {"ranked": [{"rank": n, "item_id": i, "score": 0.9 - n / 10, "domain": i.split("::")[0]} for n, i in enumerate(ids, 1)]})


def query(*rows):
    return step("QueryTool", {"items": list(rows), "missing_item_ids": [], "truncated": False})


def row(item_id, **kw):
    return {"item_id": item_id, "domain": item_id.split("::")[0], "title": f"T-{item_id}", "store": "S", "price": 1.5,
            "average_rating": 4.0, "rating_number": 7, "main_category": "Games", **kw}


def test_plan_items_keep_the_agent_order_and_take_metadata_from_query_tool():
    # QueryTool returns rows in a different order than the ranking: the ranking wins, QueryTool only fills metadata
    results = [ranked(B, A), query(row(A), row(B))]
    out = outcome_from_plan_results("req", results, question=None, max_items=10)
    assert [i["item_id"] for i in out.items] == extract_recommendations(results, 10) == [B, A]
    assert out.items[0]["title"] == f"T-{B}" and set(out.items[0]) == set(ITEM_FIELDS)
    assert "score" not in out.items[0] and out.n_steps == 2 and out.errors == [] and out.invented_ids == []


def test_max_items_cuts_from_the_top_and_duplicates_do_not_use_the_budget():
    results = [ranked(A, A, B, C)]
    out = outcome_from_plan_results("req", results, question=None, max_items=2)
    assert [i["item_id"] for i in out.items] == [A, B]


def test_items_without_a_metadata_step_only_have_their_id():
    out = outcome_from_plan_results("req", [ranked(A)], question=None, max_items=10)
    item = out.items[0]
    assert item["item_id"] == A and item["title"] is None and item["price"] is None and item["average_rating"] is None
    assert item["domain"] == "Video_Games"  # the ranker row carries the domain


def test_search_candidates_provide_metadata_and_query_tool_wins_on_conflict():
    search = step("SemanticSearchTool", {"candidates": [{**row(A), "title": "from search", "score": 3.0}]})
    out = outcome_from_plan_results("req", [search], question=None, max_items=10)
    assert out.items[0]["title"] == "from search"
    both = outcome_from_plan_results("req", [search, query(row(A, title="from query"))], question=None, max_items=10)
    assert both.items[0]["title"] == "from query"


def test_errors_are_cut_and_invented_ids_collected():
    long_error = "Traceback " + "e" * 2000
    results = [step("ItemCFTool", ok=False, error=long_error),
               step("QueryTool", ok=False, error="id(s) not found", invented_ids=["Video_Games::zzz"])]
    out = outcome_from_plan_results("req", results, question=None, max_items=10)
    assert [e["tool"] for e in out.errors] == ["ItemCFTool", "QueryTool"]
    assert len(out.errors[0]["error"]) <= 300 and out.invented_ids == ["Video_Games::zzz"] and out.items == []


def test_plan_error_becomes_a_planner_error_and_question_is_kept():
    out = outcome_from_plan_results("req", [], question=None, plan_error="ValueError: LLM did not return valid JSON " + "x" * 900)
    assert out.errors[0]["tool"] == "planner" and len(out.errors[0]["error"]) <= 300 and out.n_steps == 0
    asked = outcome_from_plan_results("req", [], question="Bạn cần loại sản phẩm nào?")
    assert asked.question == "Bạn cần loại sản phẩm nào?" and asked.n_steps == 0


def test_type1_ok_with_items_is_normalized():
    out = outcome_from_type1("req", {"ok": True, "cold_start": False, "items": [
        {"rank": 1, "item_id": A, "score": 0.5, "domain": "Video_Games", "title": "T", "price": 3.0},
        {"rank": 2, "item_id": B, "score": 0.4, "domain": "Video_Games"}]}, max_items=1)
    assert [i["item_id"] for i in out.items] == [A] and out.items[0]["title"] == "T"
    assert set(out.items[0]) == set(ITEM_FIELDS) and out.items[0]["store"] is None
    assert out.cold_start is False and out.errors == [] and out.question is None


def test_type1_failure_keeps_the_stage():
    out = outcome_from_type1("req", {"ok": False, "stage": "rank", "error": "boom " * 200})
    assert out.items == [] and out.errors[0]["tool"] == "rank" and len(out.errors[0]["error"]) <= 300


def test_type1_empty_list_records_cold_start():
    out = outcome_from_type1("req", {"ok": True, "items": [], "cold_start": True})
    assert out.items == [] and out.errors == [] and out.cold_start is True
