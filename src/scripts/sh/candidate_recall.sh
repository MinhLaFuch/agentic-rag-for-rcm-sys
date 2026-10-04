#!/usr/bin/env bash
# Candidate recall của các retrieval tool. Tham số: configs/retrieval.yaml → candidate_recall
# (ItemKNN k và seed lấy từ model.yaml → baselines). Cần resource/raw/meta_<Domain>.jsonl.gz.
#   bash scripts/sh/candidate_recall.sh
#   bash scripts/sh/candidate_recall.sh --eval-on test --n 20,50
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
"$PYTHON" scripts/py/candidate_recall.py ${TAG:+--tag "$TAG"} "$@"
