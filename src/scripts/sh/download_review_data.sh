#!/usr/bin/env bash
# Run from anywhere: the script cd-s to the project root (the folder containing package/ and scripts/).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export PYTHONPATH=".${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python}"   # e.g. PYTHON=.venv/Scripts/python bash scripts/sh/xxx.sh

# ===================== EDIT ME =====================
DOMAIN="Video_Games"          # Video_Games | Toys_and_Games | Electronics | ...
OUT_ROOT="data/raw"
# ====================================================
OUT_DIR="${OUT_ROOT}/${DOMAIN}"
mkdir -p "${OUT_DIR}"
URL="https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/review_categories/${DOMAIN}.jsonl.gz"
OUT_FILE="${OUT_DIR}/review_${DOMAIN}.jsonl.gz"

echo "Downloading: ${URL}"
echo "Output:      ${OUT_FILE}"
curl -L --fail -C - -o "${OUT_FILE}" "${URL}"
ls -lh "${OUT_FILE}"
echo "Review count:"; zcat "${OUT_FILE}" | wc -l
