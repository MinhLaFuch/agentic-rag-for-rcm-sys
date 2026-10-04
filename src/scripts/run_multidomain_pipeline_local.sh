#!/usr/bin/env bash
# Run from anywhere: the script cd-s to the project root (the folder containing package/ and scripts/).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export PYTHONPATH=".${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python}"   # e.g. PYTHON=.venv/Scripts/python bash scripts/sh/xxx.sh

# ===================== EDIT ME =====================
# Format: Name=path   (comment a line out to drop that domain)
DOMAINS=(
  "Video_Games=data/raw/Video_Games/review_Video_Games.jsonl.gz"
  "Toys_and_Games=data/raw/Toys_and_Games/review_Toys_and_Games.jsonl.gz"
  "Electronics=data/raw/Electronics/review_Electronics.jsonl.gz"
)
# ====================================================
ARGS=()
for d in "${DOMAINS[@]}"; do ARGS+=(--domain "$d"); done
"$PYTHON" scripts/run_multidomain_pipeline_local.py "${ARGS[@]}"
