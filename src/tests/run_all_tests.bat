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

REM Move up to src so that tests/config/, tests/data/, tests/agent/ resolve
cd /d ..
set PYTHONPATH=.

echo ========================================== > "%MAIN_LOG%"
echo Running All Tests - %TIMESTAMP% >> "%MAIN_LOG%"
echo ========================================== >> "%MAIN_LOG%"

REM Run tests in each subdirectory
echo. >> "%MAIN_LOG%"
echo === Running Config Tests === >> "%MAIN_LOG%"
python -m pytest tests/config/ -v --tb=short --log-cli-level=INFO >> "%MAIN_LOG%" 2>&1

echo. >> "%MAIN_LOG%"
echo === Running Data Tests === >> "%MAIN_LOG%"
python -m pytest tests/data/ -v --tb=short --log-cli-level=INFO >> "%MAIN_LOG%" 2>&1

echo. >> "%MAIN_LOG%"
echo === Running Agent Tests === >> "%MAIN_LOG%"
python -m pytest tests/agent/ -v --tb=short --log-cli-level=INFO >> "%MAIN_LOG%" 2>&1

echo. >> "%MAIN_LOG%"
echo ========================================== >> "%MAIN_LOG%"
echo All tests completed. Log saved to: %MAIN_LOG% >> "%MAIN_LOG%"
echo ========================================== >> "%MAIN_LOG%"

echo All tests completed. Log saved to: %MAIN_LOG%