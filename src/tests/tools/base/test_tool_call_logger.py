"""Logging contract (architecture.md section 4) shared by every tool."""

import json

from package.recommenders import ItemKNNRecommender
from package.tools import BaselineScorer, SimilarTool, LookupTool, RankTool, FilterTool, ToolCallLogger
from tests.tools_helpers import EL_D, VG_A, VG_B


def test_every_call_is_logged_with_required_fields(corpus):
    logger = ToolCallLogger()
    tool = LookupTool(corpus, logger=logger)
    tool(agent="single_agent", action="candidate_analysis", item_ids=[VG_A])
    tool(query="DROP TABLE items")  # failures are logged too

    assert len(logger.records) == 2
    record = logger.records[0]
    assert set(record) == {"timestamp", "agent", "action", "tool", "input_hash", "input", "output", "latency_seconds"}
    assert record["agent"] == "single_agent" and record["action"] == "candidate_analysis"
    assert record["tool"] == "LookupTool" and record["latency_seconds"] >= 0
    assert record["output"]["ok"] is True
    assert logger.records[1]["output"]["ok"] is False


def test_input_hash_is_stable_and_input_specific(corpus):
    logger = ToolCallLogger()
    tool = FilterTool(corpus, logger=logger)
    tool(filters={"price_max": 20, "min_rating": 4})
    tool(filters={"min_rating": 4, "price_max": 20})  # same content, different key order
    tool(filters={"price_max": 21})
    first, second, third = (r["input_hash"] for r in logger.records)
    assert first == second != third


def test_logger_appends_jsonl_and_records_are_json_serialisable(corpus, cf_setup, tmp_path):
    path = tmp_path / "logs" / "tool_calls.jsonl"
    logger = ToolCallLogger(path)
    interactions, user2id, item2id = cf_setup
    knn = ItemKNNRecommender(5).fit(interactions)

    LookupTool(corpus, logger=logger)(item_ids=[VG_A])
    FilterTool(corpus, logger=logger)()
    SimilarTool(knn, item2id, corpus=corpus, logger=logger)(items=[VG_A])
    RankTool(BaselineScorer(knn), user2id, item2id, corpus=corpus, logger=logger)(
        user_id="u1", candidates=[VG_B, EL_D]
    )

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert [json.loads(line)["tool"] for line in lines] == ["LookupTool", "FilterTool", "SimilarTool", "RankTool"]
    json.dumps(logger.records)  # outputs contain only plain JSON types (no numpy scalars)
