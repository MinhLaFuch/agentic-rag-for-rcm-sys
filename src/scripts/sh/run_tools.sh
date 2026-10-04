#!/usr/bin/env bash
# Chạy thử package/tools trên dữ liệu thật (splits + mapping của stage 3, meta nếu có trong resource/raw/).
#   bash scripts/sh/run_tools.sh
#   bash scripts/sh/run_tools.sh --model popularity --eval-users 100     # knn cần nhiều RAM
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
"$PYTHON" scripts/py/run_tools.py ${TAG:+--tag "$TAG"} "$@"
