"""
Connector LLM <-> tools. 3 mảnh:
  build_tool_prompt  — [1] mô tả tool, tự sinh từ Tool.description/input_schema
  PlanExecutor.plan  — [2] gọi LLMProvider, parse JSON plan
  PlanExecutor.run   — [3] chạy từng bước plan qua tool thật, nối kết quả
"""
from __future__ import annotations

import json
from typing import Any

from ..llm import LLMProvider, LLMMessage
from ..tools.base import Tool


def build_tool_prompt(tools: list[Tool]) -> str:
    # Tự sinh từ chính Tool.description/input_schema — không cần viết tay
    # lại mô tả tool ở chỗ khác (tránh 2 nguồn dễ lệch nhau, bug reco_model_tool
    # vừa sửa chính là hậu quả của việc viết "chui" trong docstring thay vì đây).
    lines = []
    for t in tools:
        lines.append(f"- {t.name}: {t.description}")
        lines.append(f"  input_schema: {json.dumps(t.input_schema, ensure_ascii=False)}")
    return "\n".join(lines)


class PlanExecutor:
    def __init__(self, llm: LLMProvider, tools: list[Tool]) -> None:
        self.llm = llm
        self.tools = {t.name: t for t in tools}

    def plan(self, user_request: str) -> list[dict[str, Any]]:
        system = (
            "Bạn là agent gợi ý sản phẩm. Có các tool sau:\n"
            f"{build_tool_prompt(list(self.tools.values()))}\n\n"
            "Trả lời CHỈ bằng JSON: 1 list các bước, mỗi bước "
            '{"tool": "<tên tool>", "args": {...}}. Không thêm chữ nào khác.'
        )
        resp = self.llm.complete(
            [LLMMessage(role="system", content=system), LLMMessage(role="user", content=user_request)],
            response_format_json=True,
        )
        try:
            steps = json.loads(resp.text)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM không trả JSON hợp lệ: {resp.text[:200]}") from e
        if not isinstance(steps, list):
            raise ValueError(f"Plan phải là list các bước, nhận được: {type(steps)}")
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
