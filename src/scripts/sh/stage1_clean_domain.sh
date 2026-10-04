#!/usr/bin/env bash
# Stage 1: clean từng domain lần lượt (domain: data.yaml → domains; chunk: cleaning.chunk_size).
# Lỗi ở một domain không làm dừng các domain còn lại.
#   bash scripts/sh/stage1_clean_domain.sh                 # tất cả domain
#   DOMAINS="Video_Games Electronics" bash scripts/sh/stage1_clean_domain.sh
#   bash scripts/sh/stage1_clean_domain.sh --force         # làm lại dù đã có output
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
parse_flags "$@"
load_domains
RAW_DIR="$(cfg data.paths.raw_dir)"
CLEANED_DIR="$(cfg data.paths.cleaned_dir)"

DONE=(); SKIPPED=(); FAILED=()

for DOMAIN in "${DOMAIN_LIST[@]}"; do
  REVIEW_PATH="${RAW_DIR}/${DOMAIN}.jsonl.gz"
  OUT_FILE="${CLEANED_DIR}/${DOMAIN}/interactions.parquet"

  echo
  echo "################ Stage 1: ${DOMAIN} ################"

  if [[ ! -f "$REVIEW_PATH" ]]; then
    echo "MISSING input: ${REVIEW_PATH} (bash scripts/sh/download_review_data.sh)"
    FAILED+=("$DOMAIN"); continue
  fi

  if [[ -f "$OUT_FILE" && "$FORCE" != true ]]; then
    echo "SKIP: ${OUT_FILE} already exists (use --force to redo)"
    SKIPPED+=("$DOMAIN"); continue
  fi

  if "$PYTHON" scripts/py/stage1_clean_domain.py --domain "$DOMAIN" ${PASS_ARGS[@]+"${PASS_ARGS[@]}"} ${FORCE_ARGS[@]+"${FORCE_ARGS[@]}"}; then
    DONE+=("$DOMAIN")
  else
    echo "FAILED: ${DOMAIN}"
    FAILED+=("$DOMAIN")
  fi
done

echo
echo "================ Stage 1 summary ================"
echo "done:    ${DONE[*]:-none}"
echo "skipped: ${SKIPPED[*]:-none}"
echo "failed:  ${FAILED[*]:-none}"
[[ ${#FAILED[@]} -eq 0 ]]   # exit khác 0 nếu có domain lỗi
