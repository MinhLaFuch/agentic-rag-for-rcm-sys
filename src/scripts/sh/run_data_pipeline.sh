#!/usr/bin/env bash
# Chạy liền Stage 1 → 2 → 3 (dữ liệu thô đã có trong resource/raw/).
# Stage đã có output thì bị bỏ qua; --force làm lại cả ba.
#   bash scripts/sh/run_data_pipeline.sh
#   DOMAINS="Video_Games Toys_and_Games" TAG=vg_toys bash scripts/sh/run_data_pipeline.sh
set -euo pipefail
here="$(dirname "${BASH_SOURCE[0]}")"
[[ $# -le 1 && "${1:---force}" == "--force" ]] || { echo "usage: run_data_pipeline.sh [--force]"; exit 2; }

bash "$here/stage1_clean_domain.sh" "$@"
bash "$here/stage2_merge_filter.sh" "$@"
bash "$here/stage3_map_split.sh" "$@"
