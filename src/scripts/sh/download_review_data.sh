#!/usr/bin/env bash
# Tải review + metadata thô của mọi domain trong configs/domains.yaml về resource/raw/.
# Resume được nếu bị ngắt giữa chừng; bỏ qua file đã có.
#   bash scripts/sh/download_review_data.sh              # review + meta, tất cả domain
#   bash scripts/sh/download_review_data.sh --no-meta    # chỉ review
#   DOMAINS="Video_Games" bash scripts/sh/download_review_data.sh
#   bash scripts/sh/download_review_data.sh --force      # tải lại từ đầu
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
parse_flags "$@"
load_domains

GET_META=true
for a in ${PASS_ARGS[@]+"${PASS_ARGS[@]}"}; do
  [[ "$a" == "--no-meta" ]] && GET_META=false
done

RAW_DIR="$(data_path raw_dir)"
REVIEW_URL="$(cfg download.download.review_url)"
META_URL="$(cfg download.download.meta_url)"
mkdir -p "$RAW_DIR"

fetch() {  # fetch <url> <out_file>
  local url="$1" out="$2"
  if [[ -f "$out" && "$FORCE" != true ]]; then
    echo "SKIP: $out already exists (use --force to redownload)"
    return 0
  fi
  [[ "$FORCE" == true ]] && rm -f "$out" "${out}.part"
  echo "Downloading: $url"
  curl -L --fail -C - -o "${out}.part" "$url"
  mv "${out}.part" "$out"
  ls -lh "$out"
}

for DOMAIN in "${DOMAIN_LIST[@]}"; do
  echo
  echo "################ Download: ${DOMAIN} ################"
  fetch "${REVIEW_URL//\{domain\}/$DOMAIN}" "$(data_path "review_path:${DOMAIN}")"
  if [[ "$GET_META" == true ]]; then
    fetch "${META_URL//\{domain\}/$DOMAIN}" "$(data_path "meta_path:${DOMAIN}")"
  fi
done
