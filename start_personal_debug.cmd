@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [Echo Score] Missing local Python environment: %CD%\.venv
    echo Please install the development environment first.
    pause
    exit /b 1
)

rem Request elevation at the launcher boundary.  Starting Python unelevated
rem and relying on a second ShellExecute from inside main_debug.py can leave
rem the desktop shortcut with only a hanging console and no application UI.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root = [IO.Path]::GetFullPath('%~dp0'); $python = Join-Path $root '.venv\Scripts\python.exe'; $script = Join-Path $root 'main_debug.py'; Start-Process -FilePath $python -ArgumentList ('"' + $script + '"') -WorkingDirectory $root -Verb RunAs"
