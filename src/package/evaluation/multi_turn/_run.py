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

    parser.parse_args()
    raise SystemExit("real runner not implemented yet")


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
