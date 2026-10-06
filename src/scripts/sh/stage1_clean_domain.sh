#!/usr/bin/env bash
# Stage 1: clean từng domain lần lượt (domain: domains.yaml → domains; chunk: cleaning.chunk_size).
# Lỗi ở một domain không làm dừng các domain còn lại.
#   bash scripts/sh/stage1_clean_domain.sh                 # tất cả domain
#   DOMAINS="Video_Games Electronics" bash scripts/sh/stage1_clean_domain.sh
#   bash scripts/sh/stage1_clean_domain.sh --force         # làm lại dù đã có output
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
parse_flags "$@"
load_domains

DONE=(); SKIPPED=(); FAILED=()

for DOMAIN in "${DOMAIN_LIST[@]}"; do
  REVIEW_PATH="$(data_path "review_path:${DOMAIN}")"
  OUT_FILE="$(data_path "cleaned_path:${DOMAIN}")"

  echo
  echo "################ Stage 1: ${DOMAIN} ################"

  if [[ ! -f "$REVIEW_PATH" ]]; then
    echo "MISSING input: ${REVIEW_PATH} — đặt file .jsonl.gz vào resource/raw/ trước khi chạy stage 1"
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
