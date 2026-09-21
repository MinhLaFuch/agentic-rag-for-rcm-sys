"""Baseline agent: 1 lần gọi LLM, không ReAct."""
from package.recommender.llm import call_llm, call_llm_mock
from package.recommender.parsing import parse_response
from package.recommender.prompt import build_prompt


def rerank(user_history_titles: list[str], candidates: list[dict], use_mock: bool = False) -> list[dict]:
    prompt = build_prompt(user_history_titles, candidates)
    raw = call_llm_mock(prompt) if use_mock else call_llm(prompt)
    ranked = parse_response(raw)
    return sorted(ranked, key=lambda x: x["rank"])
