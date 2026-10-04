#!/usr/bin/env bash
# Run from anywhere: the script cd-s to the project root (the folder containing package/ and scripts/).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export PYTHONPATH=".${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python}"   # e.g. PYTHON=.venv/Scripts/python bash scripts/sh/xxx.sh

# ===================== EDIT ME =====================
FILTERED_PATH="data/filtered/multi_domain/interactions.parquet"
MAPPING_DIR="data/mapped/multi_domain"
SPLITS_DIR="data/splits/multi_domain"
# ====================================================
"$PYTHON" scripts/py/stage3_map_split.py \
  --filtered-path "$FILTERED_PATH" \
  --mapping-dir "$MAPPING_DIR" --splits-dir "$SPLITS_DIR"
