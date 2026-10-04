from __future__ import annotations

import json
from typing import Any

from ..llm import LLMMessage, LLMProvider
from ..tools.base import Tool
from .build_tool_prompt import build_tool_prompt


class PlanExecutor:
    def __init__(self, llm: LLMProvider, tools: list[Tool]) -> None:
        self.llm = llm
        self.tools = {t.name: t for t in tools}

    def plan(self, user_request: str) -> list[dict[str, Any]]:
        system = (
            "B?n l� agent g?i � s?n ph?m. C� c�c tool sau:\n"
            f"{build_tool_prompt(list(self.tools.values()))}\n\n"
            "Tr? l?i CH? b?ng JSON: 1 list c�c b??c, m?i b??c "
            '{"tool": "<t�n tool>", "args": {...}}. Kh�ng th�m ch? n�o kh�c.'
        )
        resp = self.llm.complete(
            [LLMMessage(role="system", content=system), LLMMessage(role="user", content=user_request)],
            response_format_json=True,
        )
        try:
            steps = json.loads(resp.text)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM kh�ng tr? JSON h?p l?: {resp.text[:200]}") from e
        if not isinstance(steps, list):
            raise ValueError(f"Plan ph?i l� list c�c b??c, nh?n ???c: {type(steps)}")
        return steps

    def run(self, user_request: str) -> list[dict[str, Any]]:
        steps = self.plan(user_request)
        results = []
        for step in steps:
            tool = self.tools.get(step["tool"])
            if tool is None:
                results.append({"tool": step.get("tool"), "ok": False, "error": "unknown tool"})
                continue
            res = tool(agent="planner", **step.get("args", {}))
            results.append({"tool": step["tool"], "ok": res.ok, "data": res.data, "error": res.error})
        return results
