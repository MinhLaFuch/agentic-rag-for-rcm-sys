"""CLI runner for multi-turn conversation evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ._schema import Conversation


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
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON path (default: data_paths.outputs.multi_turn/<dataset>_<ts>.json)",
    )
    args = parser.parse_args()

    import subprocess
    from datetime import datetime, timezone

    from package.config import get_data_paths

    from ._agent_runner import RealAgentRunner
    from .multi_turn_evaluator import MultiTurnEvaluator

    git_sha = args.git_sha
    if git_sha is None:
        try:
            git_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
            ).stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            git_sha = ""

    conversations = load_conversations(args.dataset)
    print(f"Loaded {len(conversations)} conversations from {args.dataset}")

    # Real runner: real LLM + real tools + Session. Raises if no LLM config —
    # a missing provider must fail loudly, never produce fake scores.
    runner = RealAgentRunner()
    evaluator = MultiTurnEvaluator()

    summary = evaluator.evaluate_conversations(conversations, runner, git_sha=git_sha)

    if args.output:
        output_path = Path(args.output)
    else:
        output_dir = get_data_paths().output_dir("multi_turn")
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"multi_turn_{Path(args.dataset).stem}_{ts}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary.to_dict(), indent=2, default=str), encoding="utf-8")
    print(f"Results saved to: {output_path}")
    print(
        f"conversations={summary.total_conversations} "
        f"turn_success_rate={summary.turn_success_rate:.3f} "
        f"conversation_success_rate={summary.conversation_success_rate:.3f}"
    )


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


if __name__ == "__main__":
    run_multi_turn_cli()
