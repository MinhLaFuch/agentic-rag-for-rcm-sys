#!/usr/bin/env bash
# Stage 2: gộp các domain đã clean + k-core filter (MỘT lần chạy cho tất cả domain, không lặp từng domain).
#   bash scripts/sh/stage2_merge_filter.sh
#   DOMAINS="Video_Games Toys_and_Games" TAG=vg_toys bash scripts/sh/stage2_merge_filter.sh
#   bash scripts/sh/stage2_merge_filter.sh --force --cold-start-report
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
parse_flags "$@"
load_domains
resolve_tag
CLEANED_DIR="$(cfg data.paths.cleaned_dir)"
OUT_FILE="$(cfg data.paths.filtered_dir)/${TAG}/interactions.parquet"

# Dừng sớm (trước khi nạp gì vào RAM) nếu thiếu output của Stage 1.
missing=0
for d in "${DOMAIN_LIST[@]}"; do
  f="${CLEANED_DIR}/${d}/interactions.parquet"
  [[ -f "$f" ]] || { echo "MISSING Stage 1 output: $f"; missing=1; }
done
[[ $missing -eq 0 ]] || { echo "Run stage1_clean_domain.sh first."; exit 1; }

if [[ -f "$OUT_FILE" && "$FORCE" != true ]]; then
  echo "SKIP: ${OUT_FILE} already exists (use --force to redo)"
  exit 0
fi

DOMAIN_ARGS=()
for d in "${DOMAIN_LIST[@]}"; do DOMAIN_ARGS+=(--domain "$d"); done

"$PYTHON" scripts/py/stage2_merge_filter.py --tag "$TAG" "${DOMAIN_ARGS[@]}" \
  ${PASS_ARGS[@]+"${PASS_ARGS[@]}"} ${FORCE_ARGS[@]+"${FORCE_ARGS[@]}"}
echo "Stage 2 OK -> ${OUT_FILE}"
