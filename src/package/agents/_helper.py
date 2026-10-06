
from typing import Any
import re
import json
from ._schema import ID_ARG_KEYS, _REF

def _resolve_path(value: Any, parts: list[str]) -> Any:
    if not parts:
        return value
    head, rest = parts[0], parts[1:]
    if head == "*":
        if not isinstance(value, list):
            raise KeyError("'*' needs a list")
        return [_resolve_path(v, rest) for v in value]
    if isinstance(value, dict) and head in value:
        return _resolve_path(value[head], rest)
    if isinstance(value, list) and head.isdigit() and int(head) < len(value):
        return _resolve_path(value[int(head)], rest)
    raise KeyError(f"'{head}' not found")


def _resolve_refs(obj: Any, results: list[dict[str, Any]]) -> Any:
    """Thay chuỗi '$N.path' bằng output của step N; ném ValueError nếu step N lỗi/chưa chạy/path sai."""
    if isinstance(obj, str):
        m = _REF.match(obj)
        if not m:
            return obj
        n = int(m.group(1))
        if not 1 <= n <= len(results):
            raise ValueError(f"{obj}: step {n} has not run yet")
        if not results[n - 1]["ok"]:
            raise ValueError(f"{obj}: skipped, step {n} failed")  # the cause is in step n's own error
        parts = [p for p in m.group(2).split(".") if p]
        try:
            return _resolve_path(results[n - 1]["data"], parts)
        except KeyError as exc:
            raise ValueError(f"{obj}: {exc.args[0]}") from exc
    if isinstance(obj, dict):
        return {k: _resolve_refs(v, results) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_refs(v, results) for v in obj]
    return obj


def _extract_plan(text: str) -> tuple[list[dict[str, Any]], str | None]:
    # model hay bọc ```json ... ``` dù đã bật JSON mode (và có endpoint không ép JSON mode thật)
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON: {text[:200]}") from e
    question = None
    if isinstance(data, dict):  # json_object mode ép top-level là object nên list luôn đến dạng {"steps": [...]}
        question = data.get("ask_user") or None
        data = data.get("steps", data.get("plan", []))
    if not isinstance(data, list) or not all(isinstance(s, dict) for s in data):
        raise ValueError(f"Plan must be a list of steps, got: {text[:200]}")
    return data, question


def _unknown_args(tool: Any, args: Any) -> str | None:
    """Error text for args the tool does not declare (None if fine), with a hint when the key belongs in a nested dict."""
    schema = tool.input_schema
    if not isinstance(args, dict) or not schema:
        return None  # a tool without a declared schema cannot be judged
    unknown = sorted(set(args) - set(schema))
    if not unknown:
        return None
    hints = []
    for key in unknown:
        home = next((name for name, spec in schema.items() if isinstance(spec, dict) and any(key in str(k) for k in spec)), None)
        if home:
            hints.append(f"'{key}' belongs inside `{home}`")
    return f"unknown arg(s) {unknown} for {tool.name}; allowed: {sorted(schema)}" + (f" ({'; '.join(hints)})" if hints else "")


def _invented_ids(args: Any, request: str) -> list[str]:
    """Literal ids in `args` that do not appear in the request text (the prompt forbids inventing ids)."""
    if not isinstance(args, dict):
        return []
    invented: list[str] = []
    for key in ID_ARG_KEYS:
        value = args.get(key)
        literals = [value] if isinstance(value, str) else value if isinstance(value, list) else []
        for v in literals:
            if isinstance(v, str) and not _REF.match(v) and v not in request:
                invented.append(v)
    return invented
