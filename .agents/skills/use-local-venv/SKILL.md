---
name: use-local-venv
description: Prefer the repository-local Python virtual environment for coding-agent work. Use when running Python scripts, tests, linters, formatters, package installs, dependency checks, or any Python command in a repo that may contain a .venv; fall back to global Python only when no local .venv interpreter exists.
---

# Use Local Venv

## Overview

Use the project `.venv` for Python commands so agent work uses the same dependencies as the repository instead of the global Python installation.

## Rule

- Before running Python, check for a local virtual environment at the repository root.
- Prefer invoking the interpreter directly rather than relying on activation.
- Use the global `python` command only when no local `.venv` interpreter exists.

## PowerShell

Resolve the interpreter once, then call it with `&`:

```powershell
$Python = if (Test-Path ".\.venv\Scripts\python.exe") {
  ".\.venv\Scripts\python.exe"
} elseif (Test-Path ".\.venv\bin\python") {
  ".\.venv\bin\python"
} else {
  "python"
}

& $Python -m pytest
& $Python .agent/skills/github_issue_solver/scripts/github_api.py get 123
```

For one-off commands in this repository on Windows, this is usually enough:

```powershell
.\.venv\Scripts\python.exe -m unittest discover tests
```

## POSIX Shells

```bash
if [ -x "./.venv/bin/python" ]; then
  PYTHON="./.venv/bin/python"
elif [ -x "./.venv/Scripts/python.exe" ]; then
  PYTHON="./.venv/Scripts/python.exe"
else
  PYTHON="python"
fi

$PYTHON -m pytest
```
