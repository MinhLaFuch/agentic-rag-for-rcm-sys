#!/usr/bin/env bash
# Run from anywhere: the script cd-s to the project root (the folder containing package/ and scripts/).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export PYTHONPATH=".${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${PYTHON:-python}"   # e.g. PYTHON=.venv/Scripts/python bash scripts/sh/xxx.sh

# ===================== EDIT ME =====================
SPLITS_DIR="data/splits/multi_domain"
EVAL_ON="validation"                      # validation | test
MODELS="random,popularity,item_knn,bpr_mf"
KS=""                                     # e.g. "5,10,20"; empty = use evaluation.yaml
EXPERIMENTS_DIR="experiments"
# ====================================================
ARGS=(--splits-dir "$SPLITS_DIR" --eval-on "$EVAL_ON" --models "$MODELS" --experiments-dir "$EXPERIMENTS_DIR")
[[ -n "$KS" ]] && ARGS+=(--ks "$KS")
"$PYTHON" scripts/py/run_baselines.py "${ARGS[@]}"
