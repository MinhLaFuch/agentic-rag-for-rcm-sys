"""Parse output JSON của LLM."""
import json


def parse_response(raw: str) -> list[dict]:
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM trả về không đúng JSON, cần xem lại prompt hoặc thử lại: {raw[:200]}") from e
