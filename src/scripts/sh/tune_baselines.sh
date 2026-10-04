#!/usr/bin/env bash
# Tune baseline chỉ bằng validation (grid: tuning.yaml → tuning). --run-final-test: refit bản thắng
# trên train+val rồi chấm TEST đúng một lần — chỉ dùng sau khi đã xem kết quả validation.
#   bash scripts/sh/tune_baselines.sh
#   bash scripts/sh/tune_baselines.sh --models item_knn --selection-metric recall@20
#   bash scripts/sh/tune_baselines.sh --run-final-test
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
"$PYTHON" scripts/py/tune_baselines.py ${TAG:+--tag "$TAG"} "$@"
