import pytest

from package.agents import Type1Agent
from package.tools.base import Tool, ToolCallLogger, ToolInputError
from package.evaluation.requests import AgentRequest
from scripts.evaluation.run_agent_eval import run_type1


class AuditTool(Tool):
    name = "AuditTool"
    description = "fixture"
    input_schema = {"value": "any"}
    output_schema = {"value": "any"}

    def __init__(self, name, output, logger, fail=None):
        super().__init__(logger)
        self.name, self.output, self.fail = name, output, fail

    def execute(self, **kwargs):
        if self.fail:
            raise self.fail("fixture failure")
        return self.output


@pytest.mark.parametrize("failure", [None, ToolInputError, RuntimeError])
def test_type1_preserves_ordered_calls_and_failures_without_previous_request(failure):
    logger = ToolCallLogger()
    retrieve = AuditTool("SimilarTool", {"candidates": [{"item_id": "D::a"}]}, logger)
    rank = AuditTool("RankTool", {"ranked": [{"item_id": "D::a", "score": 1}], "cold_start": False}, logger, failure)
    fetch = AuditTool("LookupTool", {"items": [{"item_id": "D::a", "title": "A"}]}, logger)
    runner = Type1Agent(retrieve, rank, fetch)
    request = AgentRequest(request_id="r", kind="similar", segment="warm", text="similar", user_id="u", seed_item_id="D::seed")
    for _ in range(2):
        row = run_type1(runner, request, 1)
        expected = ["SimilarTool", "RankTool"] + ([] if failure else ["LookupTool"])
        assert [call["tool"] for call in row["tool_calls"]] == expected
        assert [step["tool"] for step in row["steps"]] == expected
        assert all(c["agent"] == "type1" and c["input_hash"] and c["timestamp"] for c in row["tool_calls"])
        assert all(c["latency_seconds"] >= 0 for c in row["tool_calls"])
        if failure:
            assert row["error"] and not row["steps"][-1]["ok"]
        else:
            assert row["recommended"] == ["D::a"]
