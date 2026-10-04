#!/usr/bin/env bash
# Run from anywhere: the script cd-s to the project root (the folder containing package/ and scripts/).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export PYTHONPATH=".${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python}"   # e.g. PYTHON=.venv/Scripts/python bash scripts/sh/xxx.sh

# ===================== EDIT ME =====================
SPLITS_DIR="data/splits/Video_Games"
MAPPING_DIR="data/mapped/Video_Games"
# Format: Domain=path_to_meta  (one per domain in the splits)
META=(
  "Video_Games=data/raw/Video_Games/meta_Video_Games.jsonl.gz"
)
EVAL_ON="validation"                      # validation | test
BUDGETS="50,100,200"                      # candidate budgets N
PER_SEGMENT=1000                          # max users sampled per segment
SEED_ITEMS=10                             # recent items used as ItemCF seeds
QUERY_ITEMS=3                             # recent item titles forming the semantic query
NEIGHBORS=20                              # ItemKNN k (match model.yaml)
SEED=42
EXPERIMENTS_DIR="experiments/candidate_recall"
# ====================================================
ARGS=()
for m in "${META[@]}"; do ARGS+=(--meta "$m"); done
"$PYTHON" scripts/candidate_recall.py "${ARGS[@]}" \
  --splits-dir "$SPLITS_DIR" --mapping-dir "$MAPPING_DIR" \
  --eval-on "$EVAL_ON" --n "$BUDGETS" --per-segment "$PER_SEGMENT" \
  --seed-items "$SEED_ITEMS" --query-items "$QUERY_ITEMS" \
  --neighbors "$NEIGHBORS" --seed "$SEED" --experiments-dir "$EXPERIMENTS_DIR"
