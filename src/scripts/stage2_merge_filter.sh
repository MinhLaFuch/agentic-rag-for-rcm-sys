#!/usr/bin/env bash
# Run from anywhere: the script cd-s to the project root (the folder containing package/ and scripts/).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export PYTHONPATH=".${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python}"   # e.g. PYTHON=.venv/Scripts/python bash scripts/sh/xxx.sh

# ===================== EDIT ME =====================
DOMAINS=(Video_Games Toys_and_Games Electronics)   # each must have finished Stage 1
CLEANED_DIR="data/cleaned"
OUTPUT_DIR="data/filtered/multi_domain"
# ====================================================
ARGS=()
for d in "${DOMAINS[@]}"; do ARGS+=(--domain "$d"); done
"$PYTHON" scripts/stage2_merge_filter.py "${ARGS[@]}" \
  --cleaned-dir "$CLEANED_DIR" --output-dir "$OUTPUT_DIR"
