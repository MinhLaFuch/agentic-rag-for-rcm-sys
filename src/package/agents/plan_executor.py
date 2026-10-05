from __future__ import annotations

import json
import re
from typing import Any

from ..llm import LLMMessage, LLMProvider
from ..tools.base import Tool
from .build_tool_prompt import build_tool_prompt
from ._config import _REF
from ._helper import _extract_plan, _resolve_refs
from ._prompt import SYSTEM_PROMPT
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
            tool = self.tools.get(name) if name else None
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