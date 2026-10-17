from __future__ import annotations

import json
import re


def parse_llm_reply(text: str) -> tuple[str, list[str]]:
    """(answer, mentioned_item_ids) from the LLM reply; ValueError when it is not the agreed JSON."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())  # models wrap JSON in a fence even in JSON mode
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid_json: the reply is not valid JSON: {text[:150]}") from exc
    if not isinstance(data, dict):
        raise ValueError("invalid_json: the reply must be a JSON object")
    answer, mentioned = data.get("answer"), data.get("mentioned_item_ids")
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("invalid_json: `answer` must be a non-empty string")
    if not isinstance(mentioned, list) or not all(isinstance(i, str) for i in mentioned):
        raise ValueError("invalid_json: `mentioned_item_ids` must be a list of strings")
    return answer, mentioned
