from __future__ import annotations

import json

from ..tools.base import Tool

def build_tool_prompt(tools: list[Tool]) -> str:
    lines = []
    for t in tools:
        lines.append(f"- {t.name}: {t.description}")
        lines.append(f"  input_schema: {json.dumps(t.input_schema, ensure_ascii=False)}")
        if t.output_schema:  # the only field names a "$N.path" reference may use
            lines.append(f"  returns: {json.dumps(t.output_schema, ensure_ascii=False)}")
    return "\n".join(lines)
