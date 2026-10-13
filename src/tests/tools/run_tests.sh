#!/bin/bash
# Run tools tests and save results to log file

set -e

# Run from this folder regardless of where the script is invoked from (logs go to tests/logs/)
cd "$(dirname "$0")"

# Create logs directory if it doesn't exist
mkdir -p ../logs

# Get current timestamp for log filename
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="../logs/tools_tests_${TIMESTAMP}.log"
RESULTS_FILE="../logs/tools_tests_results_${TIMESTAMP}.md"  # input/output of every test (see tests/results_report.py)

echo "==========================================" | tee -a "$LOG_FILE"
echo "Running Tools Tests - $TIMESTAMP" | tee -a "$LOG_FILE"
echo "==========================================" | tee -a "$LOG_FILE"

PYTHONPATH=../.. python -m pytest . -v --tb=short --log-cli-level=INFO --results-file="$RESULTS_FILE" 2>&1 | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "Tools tests completed. Log saved to: $LOG_FILE" | tee -a "$LOG_FILE"
echo "Per-test input/output saved to: $RESULTS_FILE" | tee -a "$LOG_FILE"
