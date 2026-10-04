#!/usr/bin/env bash
# Run from anywhere: the script cd-s to the project root (the folder containing package/ and scripts/).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export PYTHONPATH=".${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python}"   # e.g. PYTHON=.venv/Scripts/python bash scripts/sh/xxx.sh

# ===================== EDIT ME =====================
DOMAIN="Video_Games"
REVIEW_PATH="data/raw/${DOMAIN}/review_${DOMAIN}.jsonl.gz"
OUTPUT_DIR="data/cleaned"
CHUNK_SIZE=250000             # lower it if you run out of RAM
# ====================================================
# NOTE: aborts if ${OUTPUT_DIR}/${DOMAIN}/interactions.parquet already exists.
"$PYTHON" scripts/stage1_clean_domain.py \
  --domain "$DOMAIN" --review-path "$REVIEW_PATH" \
  --output-dir "$OUTPUT_DIR" --chunk-size "$CHUNK_SIZE"
