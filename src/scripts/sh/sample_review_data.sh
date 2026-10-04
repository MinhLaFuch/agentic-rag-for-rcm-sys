#!/usr/bin/env bash
# Run from anywhere: the script cd-s to the project root (the folder containing package/ and scripts/).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export PYTHONPATH=".${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python}"   # e.g. PYTHON=.venv/Scripts/python bash scripts/sh/xxx.sh

# ===================== EDIT ME =====================
DOMAIN="Video_Games"
INPUT="resource/raw/${DOMAIN}.jsonl.gz"
OUTPUT="resource/raw/${DOMAIN}_sample.jsonl.gz"
SAMPLE_SIZE=200000
SEED=42
# ====================================================
"$PYTHON" scripts/py/sample_review_data.py \
  --input "$INPUT" --output "$OUTPUT" \
  --sample-size "$SAMPLE_SIZE" --seed "$SEED"
