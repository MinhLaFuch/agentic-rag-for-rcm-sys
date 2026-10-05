#!/bin/bash
# Run agent tests and save results to log file

set -e

# Run from this folder regardless of where the script is invoked from (logs go to tests/logs/)
cd "$(dirname "$0")"

# Create logs directory if it doesn't exist
mkdir -p ../logs

# Get current timestamp for log filename
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="../logs/agent_tests_${TIMESTAMP}.log"

echo "==========================================" | tee -a "$LOG_FILE"
echo "Running Agent Tests - $TIMESTAMP" | tee -a "$LOG_FILE"
echo "==========================================" | tee -a "$LOG_FILE"

PYTHONPATH=../.. python -m pytest . -v --tb=short --log-cli-level=INFO 2>&1 | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "Agent tests completed. Log saved to: $LOG_FILE" | tee -a "$LOG_FILE"
