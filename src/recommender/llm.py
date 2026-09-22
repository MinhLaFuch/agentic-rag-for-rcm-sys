"""Gọi LLM (bản thật + bản mock để test)."""
import json
import os


def call_llm(prompt: str) -> str:
    import openai

    openai.api_key = os.environ["OPENAI_API_KEY"]
    openai.api_base = os.environ["OPENAI_API_BASE"]
    resp = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return resp.choices[0].message["content"]


def call_llm_mock(prompt: str) -> str:
    return json.dumps([
        {"item_idx": 2, "rank": 1, "reason": "Khớp với các phụ kiện nhạc cụ user từng xem."},
    ])
