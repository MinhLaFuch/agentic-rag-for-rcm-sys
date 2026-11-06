"""CLI runner for multi-turn conversation evaluation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

from package.config import get_data_paths

from .multi_turn_evaluator import MultiTurnEvaluator
from ._schema import Conversation


def get_git_sha() -> str:
    """Get the current git commit SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def run_multi_turn_cli() -> None:
    """CLI entrypoint for running multi-turn conversation evaluation."""
    parser = argparse.ArgumentParser(
        description="Run multi-turn conversation evaluation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dataset",
        type=str,
        required=True,
        help="Path to the conversation dataset file (JSON or JSONL)",
    )
    parser.add_argument(
        "--git-sha",
        type=str,
        default=None,
        help="Git commit SHA (auto-detected if not provided)",
    )

    args = parser.parse_args()

    # Load conversations
    print(f"Loading conversations from {args.dataset}...")
    conversations = load_conversations(args.dataset)
    print(f"Loaded {len(conversations)} conversations")

    if not conversations:
        print("No conversations to evaluate")
        return

    # Agent config will come from YAML when the real runner replaces the mock
    config: dict[str, Any] = {}

    # Get git SHA
    git_sha = args.git_sha if args.git_sha else get_git_sha()
    print(f"Git SHA: {git_sha}")

    # In a real implementation, this would instantiate the actual agent runner
    # For now, use a mock runner
    agent_runner = MockAgentRunner(config)

    # Initialize evaluator
    evaluator = MultiTurnEvaluator(config)

    # Evaluate conversations
    print(f"Evaluating {len(conversations)} conversations...")
    summary = evaluator.evaluate_conversations(
        conversations=conversations,
        agent_runner=agent_runner,
        git_sha=git_sha,
    )

    # Output path comes from data_paths.outputs.multi_turn
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    experiments_dir = get_data_paths().output_dir("multi_turn")
    experiments_dir.mkdir(parents=True, exist_ok=True)
    output_path = experiments_dir / f"conversation_results_{timestamp}.json"

    # Save results
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary.to_dict(), f, indent=2, ensure_ascii=False)

    print(f"\nMulti-turn evaluation complete!")
    print(f"Results saved to: {output_path}")
    print(f"\nSummary:")
    print(f"  Total conversations: {summary.total_conversations}")
    print(f"  Turn success rate: {summary.turn_success_rate:.2%}")
    print(f"  Conversation success rate: {summary.conversation_success_rate:.2%}")
    print(f"  Mean latency: {summary.latency['mean']:.4f}s")


def load_conversations(dataset_path: str | Path) -> list[Conversation]:
    """Load conversations from a JSON or JSONL file."""
    path = Path(dataset_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    suffix = path.suffix.lower()
    conversations: list[Conversation] = []

    if suffix == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                conversations = [Conversation.from_dict(item) for item in data]
            elif isinstance(data, dict) and "conversations" in data:
                conversations = [Conversation.from_dict(item) for item in data["conversations"]]
            else:
                raise ValueError(f"Invalid JSON format: expected list or dict with 'conversations' key")
    elif suffix == ".jsonl":
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    conversations.append(Conversation.from_dict(data))
    else:
        raise ValueError(f"Unsupported file format: {suffix}. Expected .json or .jsonl")

    return conversations


class MockAgentRunner:
    """Mock agent runner for testing multi-turn evaluation.

    In a real implementation, this would instantiate the actual Agent
    and execute turns with proper session management.
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def run_turn(self, turn_input: Any, session: Any) -> dict[str, Any]:
        """Run a single turn with the given session.

        This is a mock implementation that returns deterministic responses
        based on the turn input metadata.
        """
        scenario = turn_input.metadata.get("scenario", "unknown")

        # Mock responses based on scenario
        if scenario == "M1":
            # Price refinement
            if turn_input.position == 0:
                return {"items": ["vg_a", "vg_b", "vg_c"], "exclusions": {}}
            elif turn_input.position == 1:
                return {"items": ["vg_a"], "exclusions": {"price_max": 50}}
        elif scenario == "M2":
            # Position reference
            if turn_input.position == 0:
                return {"items": ["vg_a", "vg_b", "vg_c"], "exclusions": {}}
            elif turn_input.position == 1:
                return {"items": ["vg_b_similar"], "exclusions": {}}
        elif scenario == "M3":
            # Exclusion
            if turn_input.position == 0:
                return {"items": ["vg_a", "vg_b", "vg_c"], "exclusions": {}}
            elif turn_input.position == 1:
                return {"items": ["vg_d", "vg_e"], "exclusions": {"exclude_item_ids": ["vg_a"]}}
        elif scenario == "M4":
            # More items
            if turn_input.position == 0:
                return {"items": ["vg_a", "vg_b", "vg_c"], "exclusions": {}}
            elif turn_input.position == 1:
                return {"items": ["vg_d", "vg_e", "vg_f"], "exclusions": {"exclude_item_ids": ["vg_a", "vg_b", "vg_c"]}}
        elif scenario == "M5":
            # Clarification
            if turn_input.position == 0:
                return {"items": [], "exclusions": {}}  # No items, triggers clarification
            elif turn_input.position == 1:
                return {"items": ["vg_a", "vg_b"], "exclusions": {}}
        elif scenario == "M6":
            # Topic change
            if turn_input.position == 0:
                return {"items": ["vg_a"], "exclusions": {"price_max": 50}}
            elif turn_input.position == 1:
                return {"items": ["electronics_1", "electronics_2"], "exclusions": {}}
        elif scenario == "M7":
            # Long-term memory
            if turn_input.position == 0:
                return {"items": ["preferred_1", "preferred_2"], "exclusions": {}}
            elif turn_input.position == 1:
                return {"items": ["preferred_3", "preferred_4"], "exclusions": {}}
        elif scenario == "isolation":
            # Session isolation
            return {"items": ["vg_a", "vg_b"], "exclusions": {}}
        elif scenario == "conflict":
            # Constraint update
            if turn_input.position == 0:
                return {"items": ["vg_a"], "exclusions": {"price_max": 50}}
            elif turn_input.position == 1:
                return {"items": ["vg_a", "vg_b", "vg_c"], "exclusions": {"price_max": 100}}
        elif scenario == "recovery":
            # Error recovery
            if turn_input.position == 0:
                return {"items": ["vg_a", "vg_b"], "exclusions": {}}
            elif turn_input.position == 1:
                return {"items": [], "exclusions": {}}  # Error: no items
        else:
            # Default mock response
            return {"items": ["vg_a"], "exclusions": {}}

        return {"items": [], "exclusions": {}}


if __name__ == "__main__":
    run_multi_turn_cli()
