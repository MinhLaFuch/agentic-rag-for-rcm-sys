#!/usr/bin/env bash
# Đánh giá agent (baseline / type1 / planner / planner_memory) trên cùng tập request giả lập.
# Tham số: configs/agent_eval.yaml (LLM: llm.yaml, giới hạn executor: agent.yaml). Cần resource/raw/meta_<Domain>.jsonl.gz
# và LLM_API_KEY cho agent planner*. Chạy thử nhỏ trước, rồi mới chạy đủ:
#   bash scripts/sh/run_agent_eval.sh --per-segment 2
#   bash scripts/sh/run_agent_eval.sh --agents baseline,type1      # không gọi LLM
#   bash scripts/sh/run_agent_eval.sh --resume                     # tiếp tục lần chạy bị ngắt
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
"$PYTHON" scripts/py/run_agent_eval.py ${TAG:+--tag "$TAG"} "$@"
