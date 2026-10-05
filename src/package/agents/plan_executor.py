from __future__ import annotations

import json
import re
from typing import Any

from ..llm import LLMMessage, LLMProvider
from ..tools.base import Tool
from .build_tool_prompt import build_tool_prompt

# Prompt viết bằng tiếng Anh (ASCII) để không còn phụ thuộc encoding của file;
# model vẫn hiểu request tiếng Việt của user bình thường.
SYSTEM_PROMPT = (
    "You are a product-recommendation planning agent. Available tools:\n"
    "{tools}\n\n"
    'Reply with ONLY a JSON object: {{"steps": [{{"tool": "<tool name>", "args": {{...}}}}, ...], "ask_user": null}}.\n'
    "Rules:\n"
    "- Use only the tools above, and only the args listed in their input_schema.\n"
    "- Copy ids (user_id, item ids) exactly as they appear in the request; never invent ids.\n"
    "- A step may use the output of an earlier step by writing a reference string as an arg value: "
    '"$<step number starting at 1>.<path>", e.g. "$1.candidates" or "$2.ranked.*.item_id" '
    "(\"*\" collects that field from every element of a list). A reference must be the WHOLE value, not part of a string.\n"
    "- Reference only outputs a tool actually returned; never guess item ids.\n"
    "- To recommend items to a known user: retrieve candidates (ItemCFTool or SemanticSearchTool), then ALWAYS rank them with "
    "RecoModelTool using \"$<retrieve step>.candidates\", then fetch details with QueryTool using \"$<rank step>.ranked.*.item_id\".\n"
    "- If required information is missing (e.g. no user id and no product type), return "
    '{{"steps": [], "ask_user": "<one short question, in the user\'s language>"}} instead of guessing.\n'
    "- No text outside the JSON object.\n\n"
    "Example (user u1 bought Video_Games::x, wants similar items):\n"
    '{{"steps": [{{"tool": "ItemCFTool", "args": {{"items": ["Video_Games::x"], "top_k": 30}}}}, '
    '{{"tool": "RecoModelTool", "args": {{"user_id": "u1", "candidates": "$1.candidates", "top_k": 5}}}}, '
    '{{"tool": "QueryTool", "args": {{"item_ids": "$2.ranked.*.item_id"}}}}], "ask_user": null}}'
)


_REF = re.compile(r"^\$(\d+)((?:\.[\w*]+)*)$")  # "$1", "$1.candidates", "$2.ranked.*.item_id"


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
            raise ValueError(f"{obj}: step {n} failed ({results[n - 1]['error']})")
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


class PlanExecutor:
    def __init__(
        self,
        llm: LLMProvider,
        tools: list[Tool],
        max_tokens: int = 2048,  # 512 mặc định của provider dễ cắt cụt plan nếu model là loại reasoning
        temperature: float = 0.0,
    ) -> None:
        self.llm = llm
        self.tools = {t.name: t for t in tools}
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.last_response = None  # LLMResponse của lần plan() gần nhất (để đọc latency/token)
        self.last_plan: list[dict[str, Any]] = []
        self.last_question: str | None = None  # câu hỏi làm rõ của model khi request thiếu thông tin

    def plan(self, user_request: str) -> list[dict[str, Any]]:
        system = SYSTEM_PROMPT.format(tools=build_tool_prompt(list(self.tools.values())))
        resp = self.llm.complete(
            [LLMMessage(role="system", content=system), LLMMessage(role="user", content=user_request)],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format_json=True,
        )
        self.last_response = resp
        self.last_plan, self.last_question = _extract_plan(resp.text)
        return self.last_plan

    def run(self, user_request: str) -> list[dict[str, Any]]:
        steps = self.plan(user_request)
        results = []
        for step in steps:
            name = step.get("tool")
            tool = self.tools.get(name)
            if tool is None:
                results.append({"tool": name, "ok": False, "data": {}, "error": "unknown tool"})
                continue
            try:
                args = _resolve_refs(step.get("args") or {}, results)
                res = tool(agent="planner", **args)
            except Exception as exc:  # ref hỏng hoặc args sai tên/kiểu (TypeError...) không được làm hỏng các step còn lại
                results.append({"tool": name, "ok": False, "data": {}, "error": f"{type(exc).__name__}: {exc}"})
                continue
            results.append({"tool": name, "ok": res.ok, "data": res.data, "error": res.error})
        return results