# OK-WW macOS Foreground MVP — Stage 0 Bootstrap Record

Status: **complete**

Recorded: 2026-09-04

Scope: workspace, repository identity, integration branches, reference environment, guardrails, ignore rules, and baseline evidence only

No ScreenCaptureKit, Quartz input, application/window discovery, task compatibility, visual asset, CI, or packaging runtime implementation is included in Stage 0.

## 1. Reference host

| Item | Observed value |
|---|---|
| Architecture | Apple Silicon `arm64` |
| macOS | 15.7.9, build 24G830 |
| Python | 3.12.14 arm64 |
| Python command | `python3.12` |
| Xcode developer directory | `Xcode.app/Contents/Developer` |
| Clang | Apple clang 17.0.0, target `arm64-apple-darwin24.6.0` |
| Git | 2.55.0 |
| GitHub CLI account | `Silhouette-my` |
| Git protocol | HTTPS |

Personal absolute workspace paths are intentionally omitted from committed evidence.

## 2. Repository topology

Sibling layout:

```text
workspace/
├── okww-macos-foreground-plan/
├── ok-script/
└── ok-wuthering-waves/
```

| Repository | `origin` | `upstream` | Integration branch | Starting `upstream/master` SHA |
|---|---|---|---|---|
| `ok-script` | `https://github.com/Silhouette-my/ok-script.git` | `https://github.com/ok-oldking/ok-script.git` | `feature/macos-foreground-mvp` | `784231e1c5f57a76baf5b4c2ccdef85bbe1d5766` |
| `ok-wuthering-waves` | `https://github.com/Silhouette-my/ok-wuthering-waves.git` | `https://github.com/ok-oldking/ok-wuthering-waves.git` | `feature/macos-foreground-mvp` | `a24c30f2ec90e56e40287bb76caf7c3a52266d77` |

The existing `ok_templates` submodule was initialized at `d1b4ed8c1ca9e145c514853c14030a7358afe12c`.

## 3. Repository instructions inspected

### `ok-script`

- root `AGENTS.md`;
- `.agents/skills/commit_changes/SKILL.md`;
- `.agents/skills/use_venv/SKILL.md`.

### `ok-wuthering-waves`

- root `AGENTS.md`;
- `.agents/skills/ok-script-tasks/SKILL.md`;
- `.agents/skills/ok-script-i18n/SKILL.md`;
- `.agents/skills/use-local-venv/SKILL.md`.

Task and i18n rules become active when task/UI strings are changed; Stage 0 changes documentation and repository setup only.

## 4. Reference virtual environment

The OK-WW repository-local `.venv` was created with Python 3.12.14. Verification reported:

```text
platform.machine() = arm64
interpreter format = Mach-O 64-bit executable arm64
```

`pip` version at baseline: 26.2.1.

The sibling `ok-script` checkout is the designated editable-development source. The failed install below is retained as baseline evidence and is not bypassed.

## 5. Dependency-install baseline

### 5.1 Local editable framework install

Command:

```bash
./.venv/bin/python -m pip install -e "../ok-script[ocr,qt]"
```

Result: **failed, exit 1**.

Primary failure:

```text
ModuleNotFoundError: No module named 'get_pypi_latest_version'
```

Cause observed from repository metadata:

- `setup.py` imports `get_pypi_latest_version` when no explicit build version is supplied;
- the isolated `[build-system].requires` list does not include that package;
- the package exists only in the development dependency group, which is unavailable while the editable build requirements are being evaluated.

Assigned to: **Stage 2 — package metadata and platform-safe dependency work**.

### 5.2 OK-WW editable install

Command:

```bash
./.venv/bin/python -m pip install -e ".[dev]"
```

Result: **failed, exit 1**.

Primary failure:

```text
ok-script 2.0.5 and 2.0.6 require pywin32>=306,!=312
pywin32 has no matching distribution for macOS
ResolutionImpossible
```

Assigned to: **Stage 2 — environment markers for Windows-only dependencies**.

No `--no-deps`, temporary wheel, mutable branch URL, or global-environment workaround was used.

## 6. Import baseline

From the OK-WW checkout, commands:

```bash
./.venv/bin/python -c "import ok"
./.venv/bin/python -c "from ok.device.DeviceManager import DeviceManager"
```

Results: **both failed, exit 1**, with `ModuleNotFoundError: No module named 'ok'` because the framework installs did not complete.

A separate source-tree diagnostic was run from the sibling `ok-script` checkout with the same interpreter:

```bash
../ok-wuthering-waves/.venv/bin/python -c "import ok"
../ok-wuthering-waves/.venv/bin/python -c "from ok.device.DeviceManager import DeviceManager"
```

The first command passed only because the current working directory exposed the source tree. `DeviceManager` then failed with `ModuleNotFoundError: No module named 'cv2'`. This diagnostic is not an installation success and must not replace the later clean-environment import gate.

Assigned to: **Stage 2**. The later macOS smoke gate must additionally prove that no `win32*` implementation module is loaded.

## 7. Test baseline

Command:

```bash
./.venv/bin/python -m unittest discover -s tests -p "Test*.py"
```

Result:

```text
Ran 38 tests
FAILED (errors=27)
```

Eleven tests completed without error; 27 test modules failed to import. Primary categories:

- missing `ok` after the blocked dependency install;
- secondary missing packages such as PySide6, NumPy and OpenCV because resolution stopped;
- direct `win32api` import in `src/task/MouseResetTask.py` on macOS.

Assignments:

- install/import graph and transitive dependencies → **Stage 2**;
- direct game-layer Win32 cursor calls → framework CursorService work plus **Stage 6 OK-WW integration**;
- the full Windows regression result remains a required later CI gate and is not inferred from this Mac baseline.

## 8. Guardrails added in Stage 0

### Both repositories

- contributor-fork/upstream identity and long-lived branch policy;
- no incremental MVP PR policy;
- no submodule/vendoring connection between `ok-script` and OK-WW;
- reference Python and editable sibling workflow;
- sensitive material and build-artifact ignore rules;
- capability evidence states and no unsupported claims.

### `ok-script`

- reusable framework ownership boundary;
- platform import/dependency rules;
- persistent ScreenCaptureKit contract;
- Quartz foreground/focus guard and held-state release contract;
- coordinate, permission, shutdown, Windows regression, testing and evidence rules.

### `ok-wuthering-waves`

- normative foreground MVP constraints;
- complete integration stage sequence;
- prohibition on an OK-WW-local `win32api` compatibility shim;
- visual/resource, inference, user-facing, packaging and real-hardware acceptance boundaries.

## 9. Repository hygiene

Ignore coverage was added for:

- `.venv` where missing;
- `.DS_Store`;
- `.app`, `.dmg`, `.pkg`, `.xcarchive` and `.dSYM` products;
- signing certificate/container formats;
- notarization/codesign logs;
- TCC exports/databases;
- `.secrets` and private acceptance evidence.

No credentials, TCC data, app bundle, DMG, local absolute path, personal screenshot, or runtime implementation is included in the bootstrap commits.

## 10. Stage 0 exit checklist

- [x] Apple Silicon and supported macOS verified.
- [x] Python 3.12 arm64, Xcode/Clang and Git verified.
- [x] GitHub CLI authentication verified.
- [x] Writable contributor forks exist for both repositories.
- [x] Both independent sibling checkouts exist.
- [x] `origin` and `upstream` identities are verified.
- [x] Matching integration branches exist from recorded upstream SHAs.
- [x] Applicable repository instructions and skills were inspected.
- [x] Normative OK-WW constraints and implementation plan are present.
- [x] Framework-specific `ok-script` constraints are present.
- [x] OK-WW `.venv` exists and is Python 3.12 arm64.
- [x] Initial dependency, import and test baselines are recorded without bypasses.
- [x] `.gitignore` coverage is hardened.
- [x] Bootstrap changes are committed and pushed to contributor-fork integration branches.
- [x] No stage PR is opened.
- [x] Both source worktrees are clean after the bootstrap commits.

Stage 0 is complete. The next permitted work is Stage 1 inventory/guardrail confirmation followed by Stage 2 platform-safe packaging and import boundaries. No Mac runtime capability is claimed by this record.
