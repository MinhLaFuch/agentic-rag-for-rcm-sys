"""Step 1: audit what query strings the planner actually sends to tools.

For each run (exp_5 template, exp_11/exp_12 llm inference), extract every
SearchTool call (query, total_matches, query_tokens) and FilterTool call
(filter keys, total_matches) from trajectories. Classify query language
(vi / en / mixed / category_only / empty), report per request kind, save
ALL raw queries for the tokenizer/cap analysis.

Outputs: investigations/vi_retrieval/step1_queries.json
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent

RUNS = {
    "exp_5_template": "experiments/agent_eval/campaigns/campaign_005/"
        "exp_5_agents_planner_inference_mode_template_reflect_rounds_0_multi_turn_True/run_1",
    "exp_11_llm_r0": "experiments/agent_eval/campaigns/campaign_005/"
        "exp_11_agents_planner_memory_inference_mode_llm_reflect_rounds_0_multi_turn_True/run_1",
    "exp_12_llm_r1": "experiments/agent_eval/campaigns/campaign_005/"
        "exp_12_agents_planner_memory_inference_mode_llm_reflect_rounds_1_multi_turn_True/run_1",
}

VI_CHARS = re.compile(
    "[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ"
    "ĂÂĐÊÔƠƯÁÀẢÃẠẤẦẨẪẬẮẰẲẴẶÉÈẺẼẸẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌỐỒỔỖỘỚỜỞỠỢÚÙỦŨỤỨỪỬỮỰÝỲỶỸỴ]"
)
WORD = re.compile(r"[A-Za-zÀ-ỹĐđ]+")
STOPWORDS_EN = {
    "the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with",
    "is", "are", "be", "that", "this", "it", "as", "at", "by", "from",
    "popular", "top", "best", "new", "highly", "rated", "products", "product",
    "similar", "like", "recommend", "recommendations", "items", "item",
    "cheap", "under", "less", "than", "per", "each",
}


def lang_class(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return "empty"
    has_vi = bool(VI_CHARS.search(t))
    ascii_words = [w for w in WORD.findall(t) if w.isascii()]
    content = [w.lower() for w in ascii_words if w.lower() not in STOPWORDS_EN]
    if has_vi:
        return "mixed" if len(content) >= 3 else "vi"
    if not content:
        return "category_only"
    return "en"


def request_kind(request_id: str) -> str:
    return request_id.rsplit("-", 1)[0] if "-" in request_id else request_id


def pct(n: int, d: int) -> float:
    return round(100.0 * n / d, 1) if d else 0.0


def audit_run(run_dir: Path) -> dict:
    traj = next(run_dir.glob("*trajectories.jsonl"))
    search_lang: Counter = Counter()
    search_lang_by_kind: dict[str, Counter] = defaultdict(Counter)
    filtertool_by_kind: dict[str, int] = defaultdict(int)
    search_calls: list[dict] = []
    filter_calls: list[dict] = []
    req_lang = Counter()
    n_requests = 0
    examples: dict[str, list[str]] = defaultdict(list)

    with open(traj, encoding="utf-8") as f:
        for line in f:
            t = json.loads(line)
            n_requests += 1
            kind = request_kind(t["request_id"])
            # strip namespaced item IDs (Domain::ASIN) before language classify —
            # they contain ASCII words that would mislabel VI prose as "mixed"
            req_text = re.sub(r"\S+::\S+", " ", t.get("text", ""))
            req_text = re.sub(r"\b[A-Z0-9]{16,}\b", " ", req_text)  # user/session IDs
            # requests are Vietnamese prose with quoted English category names —
            # diacritics decide; embedded EN category phrases don't make it "mixed"
            req_lang["vi" if VI_CHARS.search(req_text) else lang_class(req_text)] += 1
            for st in t.get("steps") or []:
                tool = st.get("tool")
                args = st.get("args") or {}
                summ = st.get("output_summary") or {}
                if tool == "SearchTool":
                    q = args.get("query", "")
                    cls = lang_class(q)
                    qt = summ.get("query_tokens") or {}
                    rec = {
                        "request_id": t["request_id"], "kind": kind,
                        "query": q, "lang": cls,
                        "total_matches": summ.get("total_matches"),
                        "n_query_tokens": qt.get("n"),
                        "query_tokens": qt.get("first_ids"),
                        "dense_candidates": summ.get("dense_candidates"),
                        "latency_seconds": st.get("latency_seconds"),
                    }
                    search_calls.append(rec)
                    search_lang[cls] += 1
                    search_lang_by_kind[kind][cls] += 1
                    if len(examples[cls]) < 10 and q not in examples[cls]:
                        examples[cls].append(q)
                elif tool == "FilterTool":
                    keys = sorted(k for k, v in args.items() if v not in (None, "", []))
                    filter_calls.append({
                        "request_id": t["request_id"], "kind": kind,
                        "filter_keys": keys,
                        "total_matches": summ.get("total_matches"),
                        "applied_filters": summ.get("applied_filters"),
                    })
                    filtertool_by_kind[kind] += 1

    n_search = sum(search_lang.values())
    return {
        "n_requests": n_requests,
        "request_text_lang": dict(req_lang),
        "n_searchtool_calls": n_search,
        "search_query_lang": {k: {"n": v, "pct": pct(v, n_search)} for k, v in search_lang.most_common()},
        "search_query_lang_by_kind": {
            k: dict(v) for k, v in sorted(search_lang_by_kind.items())
        },
        "n_filtertool_calls": sum(filtertool_by_kind.values()),
        "filtertool_by_kind": dict(filtertool_by_kind),
        "search_calls": search_calls,
        "filter_calls": filter_calls,
        "search_query_examples": dict(examples),
        "total_matches": {
            "n": len([c for c in search_calls if c["total_matches"] is not None]),
            "mean": round(sum(c["total_matches"] for c in search_calls if c["total_matches"] is not None)
                          / max(1, len([c for c in search_calls if c["total_matches"] is not None])), 1),
        },
        "token_stats": {
            "queries_with_tokens": len([c for c in search_calls if c["n_query_tokens"] is not None]),
            "mean_tokens": round(sum(c["n_query_tokens"] for c in search_calls if c["n_query_tokens"] is not None)
                                 / max(1, len([c for c in search_calls if c["n_query_tokens"] is not None])), 2),
            "max_tokens": max((c["n_query_tokens"] for c in search_calls if c["n_query_tokens"] is not None), default=None),
            "over_15_tokens": len([c for c in search_calls if (c["n_query_tokens"] or 0) > 15]),
        },
    }


def main() -> None:
    out = {}
    for name, rel in RUNS.items():
        run_dir = ROOT / rel
        if not run_dir.is_dir():
            print(f"SKIP {name}: missing", file=sys.stderr)
            continue
        print(f"auditing {name} ...", file=sys.stderr)
        out[name] = audit_run(run_dir)

    (OUT / "step1_queries.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    for name, r in out.items():
        print(f"\n=== {name} ({r['n_requests']} requests) ===")
        print(" request-text lang:", r["request_text_lang"])
        print(f" SearchTool calls={r['n_searchtool_calls']} lang={r['search_query_lang']}")
        print(f" FilterTool calls={r['n_filtertool_calls']}")
        print(" total_matches mean:", r["total_matches"], "| token stats:", r["token_stats"])
        for cls, exs in r["search_query_examples"].items():
            print(f"  examples[{cls}]:")
            for e in exs[:6]:
                print("   -", e[:110])


if __name__ == "__main__":
    main()
