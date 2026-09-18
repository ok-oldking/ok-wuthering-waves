@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [Echo Score] Missing local Python environment: %CD%\.venv
    echo Please install the development environment first.
    pause
    exit /b 1
)

start "Echo Score Development" ".venv\Scripts\python.exe" "main_debug.py"
