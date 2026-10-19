from typing import Any
import re
import json
from ._schema import ID_ARG_KEYS, _REF
from .._limits import get_agent_limits
from ..results import extract_recommendations
from ...tools import get_tool_limits

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
            # List available fields from the step's output
            step_data = results[n - 1]["data"]
            tool_name = results[n - 1].get("tool", "unknown")
            if isinstance(step_data, dict):
                available = _format_available_fields(step_data)
                raise ValueError(
                    f"{obj}: {exc.args[0]}. "
                    f"Step {n} ({tool_name}) returned: {available}"
                ) from exc
            else:
                raise ValueError(f"{obj}: {exc.args[0]}") from exc
    if isinstance(obj, dict):
        return {k: _resolve_refs(v, results) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_refs(v, results) for v in obj]
    return obj


def _format_available_fields(data: dict[str, Any], indent: int = 0) -> str:
    """Format available fields from step output for error messages."""
    parts = []
    for key, value in data.items():
        if isinstance(value, dict):
            sub = _format_available_fields(value, indent + 1)
            parts.append(f"{key}: {{{sub}}}")
        elif isinstance(value, list):
            if value and isinstance(value[0], dict):
                sub = _format_available_fields(value[0], indent + 1)
                parts.append(f"{key}: [{{{sub}}}, ...]")
            else:
                parts.append(f"{key}: list[{len(value)}]")
        else:
            parts.append(key)
    return ", ".join(parts)


def _extract_plan(text: str) -> tuple[list[dict[str, Any]], str | None]:
    if text is None or (isinstance(text, str) and not text.strip()):
        raise ValueError("LLM returned None or empty text")
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


def _is_time_budget(error: Any) -> bool:
    return isinstance(error, str) and ("time budget" in error or "SQLTimeOutError" in error)


def _blocks_reflect(results: list[dict[str, Any]]) -> bool:
    """No reflect after an invented id (it must not be 'fixed' into another id) or a SQL timeout (a new plan does not help)."""
    return any(r.get("invented_ids") or _is_time_budget(r.get("error")) for r in results)


def _reflect_problem(results: list[dict[str, Any]], question: str | None) -> str | None:
    """Why this run needs a corrected plan (None = fine): a failed step, or no item at all for a plan that is not ask_user."""
    if any(not r["ok"] for r in results):
        return "at least one step failed."
    if not question and not extract_recommendations(results, 1):
        return "no step returned any item (empty results), so there is nothing to recommend."
    return None


def _step_report(results: list[dict[str, Any]]) -> str:
    """One line per step: errors cut short; for ok steps only the keys of `data` (lists with their length), never the data."""
    lines = []
    for n, r in enumerate(results, 1):
        if r["ok"]:
            keys = ", ".join(f"{k}[{len(v)}]" if isinstance(v, list) else k for k, v in r["data"].items())
            lines.append(f"{n}. {r['tool']}: ok, returned {keys or 'nothing'}")
        else:
            lines.append(f"{n}. {r['tool']}: FAILED: {str(r['error'])[:get_agent_limits().reflect_error_chars]}")
    return "\n".join(lines)


def _summarize_output(data: dict[str, Any], tool_name: str) -> dict[str, Any]:
    """Summarize tool output for trajectory logging: size + sample data, cut to max_output_summary_chars."""
    limits = get_tool_limits()
    max_chars = limits.max_output_summary_chars
    summary: dict[str, Any] = {}

    # MemoryTool output is small, include whole thing
    if tool_name == "MemoryTool":
        summary = data.copy()
    else:
        # For other tools, summarize list-like fields (candidates, ranked, items)
        for key, value in data.items():
            if isinstance(value, list):
                if value:
                    summary[key] = {
                        "n": len(value),
                        "first_ids": [v.get("item_id") if isinstance(v, dict) else v for v in value[:3]],
                        "keys": list(value[0].keys()) if isinstance(value[0], dict) else ["item_id"],
                    }
                else:
                    summary[key] = {"n": 0, "first_ids": [], "keys": []}
            elif isinstance(value, (str, int, float, bool, type(None))):
                summary[key] = value
            elif isinstance(value, dict):
                summary[key] = {k: v for k, v in value.items() if isinstance(v, (str, int, float, bool, type(None)))}

    # Cut string values to max_chars
    def _cut(obj: Any) -> Any:
        if isinstance(obj, str) and len(obj) > max_chars:
            return obj[:max_chars] + "..."
        if isinstance(obj, dict):
            return {k: _cut(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_cut(v) for v in obj]
        return obj

    return _cut(summary)


def _simplify_args_for_log(args: dict[str, Any]) -> dict[str, Any]:
    """Simplify resolved args for trajectory logging: truncate long lists, keep structure."""
    simplified = {}
    for key, value in args.items():
        if isinstance(value, (list, tuple)):
            if len(value) > 5:
                simplified[key] = f"<{type(value).__name__} length={len(value)} first_3={value[:3]}>"
            else:
                simplified[key] = value
        elif isinstance(value, dict):
            simplified[key] = {k: v for k, v in list(value.items())[:5]}
        elif isinstance(value, str) and len(value) > 100:
            simplified[key] = value[:100] + "..."
        else:
            simplified[key] = value
    return simplified
