@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [OKWW] Missing local Python environment: %CD%\.venv
    echo Please install the development environment first.
    pause
    exit /b 1
)

start "OKWW Personal Development" ".venv\Scripts\python.exe" "main_debug.py"
