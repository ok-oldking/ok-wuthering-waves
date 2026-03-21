# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

An image-recognition-based automation tool for "Wuthering Waves" (鸣潮), a Chinese action RPG. Automates repetitive tasks (daily farms, echo farming, combat) using computer vision and Windows UI automation. Windows-only; simulates input via PostMessage without memory reading or file modification.

Built on the `ok-script` framework with PySide6 GUI.

## Commands

```bash
# Run (release)
python main.py

# Run (debug)
python main_debug.py

# CLI: run task 1 and exit
ok-ww.exe -t 1 -e

# Install dependencies
pip install -r requirements.txt --upgrade

# Run tests
./run_tests.ps1
# or
python -m unittest tests/Test*.py
```

## Architecture

### Entry Points
- **`main.py`** / **`main_debug.py`**: Create `OK` instance from `ok-script`, load `config.py`, start GUI
- **`config.py`**: Central config — defines all tasks (`onetime_tasks`, `trigger_tasks`), game window settings, OCR backend, input method

### Core Source (`src/`)

**`task/`** — Task implementations (~20 tasks):
- `BaseWWTask.py`: Abstract base for all tasks; game state methods, navigation, configuration
- `BaseCombatTask.py`: Combat execution framework, character switching, skill cooldowns
- `AutoCombatTask.py`: Trigger task for automatic combat (uses `CombatCheck`)
- Other tasks: `DailyTask`, `FarmEchoTask`, `AutoRogueTask`, `AutoPickTask`, `SkipDialogTask`, etc.

**`char/`** — Character definitions (~35 characters):
- `BaseChar.py`: Abstract character class with skill definitions, cooldown management, priority system
- `CharFactory.py`: Factory pattern for character instantiation
- Individual character files implement `do_get_switch_priority()`, `do_perform()`, etc.

**`combat/`**:
- `CombatCheck.py`: Combat state analysis and enemy detection

**Other key files:**
- `src/scene/WWScene.py`: Game scene state management
- `src/globals.py`: YOLO echo detection model singleton and login state
- `src/Labels.py`: Image detection labels
- `src/OnnxYolo8Detect.py` / `src/OpenVinoYolo8Detect.py`: YOLO inference backends

### Task Types
- **Onetime tasks**: Run once per session (DailyTask, FarmEchoTask, AutoRogueTask, etc.)
- **Trigger tasks**: Run continuously in background (AutoCombatTask, AutoPickTask, AutoDialogTask, etc.)

### Detection Stack
- YOLO object detection via ONNX or OpenVINO backend (`assets/echo_model/echo.onnx`)
- Template matching with configurable variance
- OCR via `onnxocr-ppocrv5`

### Key Design Constraints
- Requires Python 3.12
- Windows-only (PostMessage API, pywin32)
- Game window: minimum 1600x900, 16:9 aspect ratio
- Background operation supported (game window can be minimized)

### i18n
Translations in `i18n/` for zh_CN, zh_TW, ja_JP, ko_KR, es_ES. Use existing translation keys when adding user-visible strings.

### Tests
Test files follow `Test*.py` naming in `tests/`. Test images for OCR/detection in `tests/images/`.
