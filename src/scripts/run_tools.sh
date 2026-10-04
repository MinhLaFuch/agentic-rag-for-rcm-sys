#!/usr/bin/env bash
# Run from anywhere: the script cd-s to the project root (the folder containing package/ and scripts/).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export PYTHONPATH=".${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python}"   # e.g. PYTHON=.venv/Scripts/python bash scripts/sh/xxx.sh

# ===================== EDIT ME =====================
SPLITS_DIR="data/splits/multi_domain"
MAPPING_DIR="data/mapped/multi_domain"
META=(                                    # leave empty () to use stage-3 output only
  "Video_Games=data/raw/Video_Games/meta_Video_Games.jsonl.gz"
  "Electronics=data/raw/Electronics/meta_Electronics.jsonl.gz"
)
MODEL="knn"                               # knn | popularity (knn needs lots of RAM)
NEIGHBORS=20
EVAL_USERS=200
NEGATIVES=99
SEED=0
# ====================================================
ARGS=()
for m in "${META[@]}"; do ARGS+=(--meta "$m"); done
"$PYTHON" scripts/run_tools.py "${ARGS[@]}" \
  --splits-dir "$SPLITS_DIR" --mapping-dir "$MAPPING_DIR" \
  --model "$MODEL" --neighbors "$NEIGHBORS" \
  --eval-users "$EVAL_USERS" --negatives "$NEGATIVES" --seed "$SEED"
