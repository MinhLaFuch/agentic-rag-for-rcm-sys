@echo off
REM Run data tests and save results to log file

setlocal enabledelayedexpansion

REM Run from this folder regardless of where the script is invoked from (logs go to tests\logs)
cd /d "%~dp0"

REM Create logs directory if it doesn't exist
if not exist ..\logs mkdir ..\logs

REM Get current timestamp for log filename
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set TIMESTAMP=%datetime:~0,8%_%datetime:~8,6%
set LOG_FILE=..\logs\data_tests_%TIMESTAMP%.log
REM Input/output of every test (see tests\results_report.py)
set RESULTS_FILE=..\logs\data_tests_results_%TIMESTAMP%.md

echo ========================================== > %LOG_FILE%
echo Running Data Tests - %TIMESTAMP% >> %LOG_FILE%
echo ========================================== >> %LOG_FILE%

set PYTHONPATH=..\..
python -m pytest . -v --tb=short --log-cli-level=INFO --results-file=%RESULTS_FILE% >> %LOG_FILE% 2>&1

echo. >> %LOG_FILE%
echo Data tests completed. Log saved to: %LOG_FILE% >> %LOG_FILE%

echo Data tests completed. Log saved to: %LOG_FILE%
echo Per-test input/output saved to: %RESULTS_FILE%
