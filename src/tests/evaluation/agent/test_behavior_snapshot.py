"""Behavior snapshot test: ensures refactoring does not change scoring behavior."""

import json
import math
from pathlib import Path

import numpy as np
import pytest

from package.evaluation.agent import AgentRequest, score_trajectory, summarize
from tests.evaluation.agent.test_agent_eval import ITEM2ID, _step, _trajectory
from tests.tools_helpers import VG_A, VG_B, VG_C, EL_A

SNAPSHOT_FILE = Path(__file__).parent / "behavior_snapshot.json"


def _make_comprehensive_trajectories():
    """Generate synthetic trajectories covering all edge cases."""
    trajectories = []
    
    # Agent combinations: baseline, type1, planner, planner_memory
    agents = ["baseline", "type1", "planner", "planner_memory"]
    
    # Kinds: similar, personalized, constrained, cold_text, ambiguous
    kinds = ["similar", "personalized", "constrained", "cold_text", "ambiguous"]
    
    idx = 0
    for agent in agents:
        for kind in kinds:
            is_planner = agent in ("planner", "planner_memory")
            has_memory = agent == "planner_memory"
            
            # Basic request
            request = AgentRequest(
                request_id=f"{agent}-{kind}-{idx}",
                kind=kind,
                segment="warm" if kind != "cold_text" else "cold",
                text=f"test {kind}",
                user_id="u1" if kind != "ambiguous" else None,
                targets=[1] if kind != "ambiguous" else [],
                price_max=20.0 if kind == "constrained" else None,
                category="Accessories" if kind in ("constrained", "cold_text") else None,
            )
            
            # Case 1: Normal success
            if kind != "ambiguous":
                tools = ["MemoryTool", "SemanticSearchTool", "RecoModelTool"] if has_memory else ["ItemCFTool", "RecoModelTool"]
                if kind == "constrained":
                    tools = ["SemanticSearchTool", "RecoModelTool"]
                steps = [_step(tools[0]), _step(tools[-1])] if is_planner else []
                traj = _trajectory(agent=agent, steps=steps, recommended=[VG_A, VG_B], tools=tools)
                traj.update(answer="test answer", answer_status="ok", answer_grounded=True, answer_fallback=False,
                           inference_usage={"attempts": 1, "prompt_tokens": 10, "completion_tokens": 5, "latency_seconds": 0.3})
                trajectories.append((request, traj))
                idx += 1
            
            # Case 2: Ambiguous - ask user
            if kind == "ambiguous":
                traj = _trajectory(agent=agent, ask_user="What do you want?", tools=[])
                trajectories.append((request, traj))
                idx += 1
            
            # Case 3: Answer status variants (only for planners)
            if is_planner and kind != "ambiguous":
                for status in ["ask_user", "no_result", "tool_error"]:
                    tools = ["ItemCFTool", "RecoModelTool"]
                    traj = _trajectory(agent=agent, steps=[_step(tools[0]), _step(tools[-1])], recommended=[VG_A], tools=tools)
                    traj.update(answer="test", answer_status=status, answer_grounded=(status == "ok"),
                               answer_fallback=(status == "ok"), inference_usage={"attempts": 1, "prompt_tokens": 10, "completion_tokens": 5, "latency_seconds": 0.3})
                    request2 = AgentRequest(request_id=f"{agent}-{kind}-{idx}", kind=kind, segment="warm", text="t", targets=[1])
                    trajectories.append((request2, traj))
                    idx += 1
            
            # Case 4: Old trajectory without answer/inference fields
            if kind != "ambiguous":
                tools = ["ItemCFTool", "RecoModelTool"]
                traj = _trajectory(agent=agent, steps=[_step(tools[0]), _step(tools[-1])] if is_planner else [], recommended=[VG_A], tools=tools)
                # Remove new fields
                for key in ["answer", "answer_status", "answer_grounded", "answer_fallback", "inference_usage"]:
                    traj.pop(key, None)
                request3 = AgentRequest(request_id=f"{agent}-{kind}-{idx}", kind=kind, segment="warm", text="t", targets=[1])
                trajectories.append((request3, traj))
                idx += 1
            
            # Case 5: Plan error
            if is_planner and kind != "ambiguous":
                traj = _trajectory(agent=agent, error="ValueError: bad plan", tools=[])
                request4 = AgentRequest(request_id=f"{agent}-{kind}-{idx}", kind=kind, segment="warm", text="t", targets=[1])
                trajectories.append((request4, traj))
                idx += 1
            
            # Case 6: Deduplicated recommendations
            if kind != "ambiguous":
                tools = ["ItemCFTool", "RecoModelTool"]
                traj = _trajectory(agent=agent, steps=[_step(tools[0]), _step(tools[-1])] if is_planner else [], recommended=[VG_A, VG_A, VG_B], tools=tools)
                request5 = AgentRequest(request_id=f"{agent}-{kind}-{idx}", kind=kind, segment="warm", text="t", targets=[1])
                trajectories.append((request5, traj))
                idx += 1
            
            # Case 7: Missing targets (ranking should be None)
            if kind != "ambiguous":
                tools = ["ItemCFTool", "RecoModelTool"]
                traj = _trajectory(agent=agent, steps=[_step(tools[0]), _step(tools[-1])] if is_planner else [], recommended=[VG_A], tools=tools)
                request6 = AgentRequest(request_id=f"{agent}-{kind}-{idx}", kind=kind, segment="warm", text="t", targets=[])
                trajectories.append((request6, traj))
                idx += 1
    
    return trajectories





def test_behavior_snapshot_and_save(tmp_path, corpus):
    """Generate and save behavior snapshot for later comparison."""
    trajectories = _make_comprehensive_trajectories()
    
    # Score all trajectories
    rows = []
    for request, traj in trajectories:
        row = score_trajectory(request, traj, item2id=ITEM2ID, corpus=corpus, k=2)
        rows.append(row)
    
    # Summarize
    summary = summarize(rows)
    
    # Convert to JSON-serializable format
    snapshot = {
        "rows": rows,
        "summary": summary,
    }
    
    # Save snapshot
    snapshot_path = tmp_path / "behavior_snapshot.json"
    with open(snapshot_path, "w") as f:
        json.dump(snapshot, f, indent=2, default=str)
    
    # Also save to the expected location if this is the first run
    if not SNAPSHOT_FILE.exists():
        SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SNAPSHOT_FILE, "w") as f:
            json.dump(snapshot, f, indent=2, default=str)
    
    # Verify snapshot has data
    assert len(rows) > 0
    assert len(summary) > 0
    
    # Check key columns exist
    sample_row = rows[0]
    expected_id_keys = {"request_id", "agent", "kind", "segment"}
    assert expected_id_keys.issubset(sample_row.keys())
    
    # Check ranking columns for non-ambiguous requests with targets
    for row in rows:
        if row["kind"] != "ambiguous" and row.get("request_id", "").startswith("baseline-similar-0"):
            assert f"precision@2" in row
            assert f"recall@2" in row


def test_behavior_snapshot_matches_existing(corpus):
    """Verify current behavior matches the saved snapshot."""
    if not SNAPSHOT_FILE.exists():
        pytest.skip(f"Snapshot file {SNAPSHOT_FILE} does not exist. Run test_behavior_snapshot_and_save first.")
    
    with open(SNAPSHOT_FILE, "r") as f:
        expected = json.load(f)
    
    trajectories = _make_comprehensive_trajectories()
    
    # Score all trajectories
    rows = []
    for request, traj in trajectories:
        row = score_trajectory(request, traj, item2id=ITEM2ID, corpus=corpus, k=2)
        rows.append(row)
    
    # Summarize
    summary = summarize(rows)
    
    # Compare rows
    assert len(rows) == len(expected["rows"]), f"Row count mismatch: {len(rows)} vs {len(expected['rows'])}"
    
    for i, (actual_row, expected_row) in enumerate(zip(rows, expected["rows"])):
        assert actual_row.keys() == expected_row.keys(), f"Row {i} keys mismatch"
        for key in actual_row.keys():
            actual_val = actual_row[key]
            expected_val = expected_row[key]
            # Handle NaN and floating point comparison
            if isinstance(actual_val, float) and isinstance(expected_val, float):
                if math.isnan(actual_val) and math.isnan(expected_val):
                    continue
                assert actual_val == pytest.approx(expected_val, rel=1e-6), f"Row {i}, key {key}: {actual_val} vs {expected_val}"
            else:
                assert actual_val == expected_val, f"Row {i}, key {key}: {actual_val} vs {expected_val}"
    
    # Compare summary
    assert summary.keys() == expected["summary"].keys()
    for agent in summary:
        assert summary[agent].keys() == expected["summary"][agent].keys()
        for kind in summary[agent]:
            assert summary[agent][kind].keys() == expected["summary"][agent][kind].keys()
            for segment in summary[agent][kind]:
                actual_seg = summary[agent][kind][segment]
                expected_seg = expected["summary"][agent][kind][segment]
                assert actual_seg.keys() == expected_seg.keys()
                for key in actual_seg:
                    actual_val = actual_seg[key]
                    expected_val = expected_seg[key]
                    if isinstance(actual_val, float) and isinstance(expected_val, float):
                        if math.isnan(actual_val) and math.isnan(expected_val):
                            continue
                        assert actual_val == pytest.approx(expected_val, rel=1e-6), f"Summary {agent}/{kind}/{segment}/{key}: {actual_val} vs {expected_val}"
                    else:
                        assert actual_val == expected_val, f"Summary {agent}/{kind}/{segment}/{key}: {actual_val} vs {expected_val}"
