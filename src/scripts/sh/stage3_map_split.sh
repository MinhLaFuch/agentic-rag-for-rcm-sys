#!/usr/bin/env bash
# Stage 3: ID mapping + temporal split + leakage check (MỘT lần chạy trên output của Stage 2).
#   bash scripts/sh/stage3_map_split.sh
#   TAG=vg_toys bash scripts/sh/stage3_map_split.sh      # TAG phải khớp Stage 2
#   bash scripts/sh/stage3_map_split.sh --force
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
parse_flags "$@"
resolve_tag
FILTERED_PATH="$(data_path filtered_path)"
SPLITS_DIR="$(data_path splits_dir)"

[[ -f "$FILTERED_PATH" ]] || { echo "MISSING Stage 2 output: ${FILTERED_PATH} (run stage2_merge_filter.sh with the same TAG)"; exit 1; }

if [[ -f "$(data_path split_path:train)" && "$FORCE" != true ]]; then
  echo "SKIP: splits already exist in ${SPLITS_DIR} (use --force to redo)"
  exit 0
fi

"$PYTHON" scripts/py/stage3_map_split.py --tag "$TAG" ${PASS_ARGS[@]+"${PASS_ARGS[@]}"} ${FORCE_ARGS[@]+"${FORCE_ARGS[@]}"}
echo "Stage 3 OK -> ${SPLITS_DIR}"
