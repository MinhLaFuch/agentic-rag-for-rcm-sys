@echo off
REM Run all tests and save results to log files

setlocal enabledelayedexpansion

REM Change to the directory where this script is located (src\tests)
cd /d "%~dp0"

REM Activate virtual environment if it exists (venv is at repo root)
if exist "..\..\.venv\Scripts\activate.bat" (
    call "..\..\.venv\Scripts\activate.bat"
)

REM Create logs directory if it doesn't exist (absolute path, so it survives the cd below)
if not exist logs mkdir logs
set "LOG_DIR=%CD%\logs"

REM Get current timestamp (PowerShell instead of wmic, which is removed on newer Windows)
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set TIMESTAMP=%%I
set "MAIN_LOG=%LOG_DIR%\test_run_%TIMESTAMP%.log"
REM Input/output of EVERY test in one file (see tests\results_report.py)
set "RESULTS_FILE=%LOG_DIR%\test_results_%TIMESTAMP%.md"

REM Move up to src so that tests/config/, tests/data/, tests/agents/ resolve
cd /d ..
set PYTHONPATH=.

echo ========================================== > "%MAIN_LOG%"
echo Running All Tests - %TIMESTAMP% >> "%MAIN_LOG%"
echo ========================================== >> "%MAIN_LOG%"

REM One pytest run over every folder (config, data, agent, ...) so there is exactly ONE results file
echo. >> "%MAIN_LOG%"
python -m pytest tests/ -v --tb=short --log-cli-level=INFO --results-file="%RESULTS_FILE%" >> "%MAIN_LOG%" 2>&1

echo. >> "%MAIN_LOG%"
echo ========================================== >> "%MAIN_LOG%"
echo All tests completed. Log saved to: %MAIN_LOG% >> "%MAIN_LOG%"
echo ========================================== >> "%MAIN_LOG%"

echo All tests completed. Log saved to: %MAIN_LOG%
echo Per-test input/output saved to: %RESULTS_FILE%
