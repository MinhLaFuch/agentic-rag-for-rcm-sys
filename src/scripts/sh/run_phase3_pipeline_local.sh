#!/usr/bin/env bash
# Run from anywhere: the script cd-s to the project root (the folder containing package/ and scripts/).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export PYTHONPATH=".${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python}"   # e.g. PYTHON=.venv/Scripts/python bash scripts/sh/xxx.sh

# ===================== EDIT ME =====================
export DOMAIN="Video_Games"   # for single-domain workflow (reads ${DOMAIN})
REVIEW_PATH="resource/raw/${DOMAIN}.jsonl.gz"
# ====================================================
"$PYTHON" scripts/py/run_phase3_pipeline_local.py --review-path "$REVIEW_PATH"
