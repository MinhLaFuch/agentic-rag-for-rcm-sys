#!/usr/bin/env bash
# Wrapper around prepare_steam.py — set DATA_DIR (required) and optionally
# override the other pipeline parameters below, then run this script.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DATA_DIR="${DATA_DIR:?Set DATA_DIR to the dataset directory, e.g. DATA_DIR=~/blob/raw_datasets/steam ./run_prepare_steam.sh}"
REVIEW_FILE="${REVIEW_FILE:-steam_reviews.json.gz}"
META_FILE="${META_FILE:-steam_games.json.gz}"
ALL_META_FILE="${ALL_META_FILE:-steam_games.csv}"
PROCESSED_SUBDIR="${PROCESSED_SUBDIR:-processed}"
OUTPUT_SUBDIR="${OUTPUT_SUBDIR:-chatbot}"
USER_K="${USER_K:-5}"
ITEM_K="${ITEM_K:-5}"
MAX_HISTORY_LEN="${MAX_HISTORY_LEN:-10}"
MAX_TITLE_LEN="${MAX_TITLE_LEN:-50}"
SIMULATOR_SAMPLE_N="${SIMULATOR_SAMPLE_N:-900}"
SEED="${SEED:-2024}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

python3 "${SCRIPT_DIR}/prepare_steam.py" \
  --data_dir "${DATA_DIR}" \
  --review_file "${REVIEW_FILE}" \
  --meta_file "${META_FILE}" \
  --all_meta_file "${ALL_META_FILE}" \
  --processed_subdir "${PROCESSED_SUBDIR}" \
  --output_subdir "${OUTPUT_SUBDIR}" \
  --user_k "${USER_K}" \
  --item_k "${ITEM_K}" \
  --max_history_len "${MAX_HISTORY_LEN}" \
  --max_title_len "${MAX_TITLE_LEN}" \
  --simulator_sample_n "${SIMULATOR_SAMPLE_N}" \
  --seed "${SEED}" \
  --log_level "${LOG_LEVEL}"
