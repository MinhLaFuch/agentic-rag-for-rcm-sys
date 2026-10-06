#!/usr/bin/env bash
# Kiểm tra kết nối LLM provider. Không có tham số: đổi provider/model trong configs/agent/llm.yaml.
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
"$PYTHON" scripts/py/check_llm_provider.py
