# Chạy:
#   bash scripts/download_review_data.sh Video_Games
#
# Nếu muốn domain khác, xem danh sách đầy đủ tại:
#   https://amazon-reviews-2023.github.io/

set -euo pipefail

DOMAIN="${Video_Games}"
OUT_DIR="data/raw/${DOMAIN}"
mkdir -p "${OUT_DIR}"

REVIEW_URL="https://datarepo.eng.ucsd.edu/mcauley_group/data/amazon_2023/raw/review_categories/${DOMAIN}.jsonl.gz"
OUT_FILE="${OUT_DIR}/review_${DOMAIN}.jsonl.gz"

echo "Downloading: ${REVIEW_URL}"
echo "Output:      ${OUT_FILE}"

curl -L --fail -C - -o "${OUT_FILE}" "${REVIEW_URL}"

echo "Done. File size:"
ls -lh "${OUT_FILE}"

echo ""
echo "Số dòng (số review) trong file:"
zcat "${OUT_FILE}" | wc -l
