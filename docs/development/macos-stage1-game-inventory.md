# macOS Foreground MVP — Stage 1 OK-WW Game Integration Inventory

Status: **complete**

Recorded: 2026-09-04

Scanned branch: `feature/macos-foreground-mvp`

Pre-Stage-1 HEAD: `988812769b2d1390555a2f4ece63bc6a7e84e8c4`

Starting `upstream/master`: `a24c30f2ec90e56e40287bb76caf7c3a52266d77`

This inventory maps current game-repository portability blockers to implementation stages. It changes no runtime behavior and claims no macOS automation support.

> 方向更新（2026-09-04）：本文件保留为 Stage 1 历史审计。后续任务能力分级、relative mouse 门槛和 A–H 实施顺序以 `MACOS_ENGINEERING_CONSTRAINTS.md`、`docs/development/macos-work-branch-direction-audit.md`、`docs/development/macos-capability-matrix.md` 与 `docs/development/macos-foreground-port-plan.md` 为准。relative mouse 不再是所有 Mac MVP/战斗/移动任务的统一阻断项。

## 1. Scope confirmation

The contributor branch remains bound to `MACOS_ENGINEERING_CONSTRAINTS.md`:

- official native Wuthering Waves Mac client;
- Apple Silicon, macOS 13+, Python 3.12 arm64;
- ScreenCaptureKit selected-window capture and Quartz foreground input supplied by `ok-script`;
- no background/minimized operation, virtual display, private API, process injection, hook, `CGEvent.postToPid`, TCC modification, root bypass, or global-input fallback;
- task code uses framework services instead of direct OS APIs;
- focus/target/capture/geometry/permission/task/application invalidation stops ordinary input and releases held state;
- Windows behavior is preserved.

No conflict was found among `AGENTS.md`, `MACOS_ENGINEERING_CONSTRAINTS.md`, the implementation plan, or the framework inventory. This is contributor scope confirmation, not a claim that upstream maintainers have already accepted the design. Upstream acceptance remains a final-PR gate.

At scan time both integration branches were one Stage 0 documentation commit ahead of, and zero commits behind, their recorded upstream bases.

## 2. Dependency and packaging inventory

| ID | Location | Finding | Impact | Assigned work |
|---|---|---|---|---|
| GAME-PKG-01 | `pyproject.toml` | OK-WW depends on `ok-script[ocr,qt]>=2.0.5`. Published 2.0.5/2.0.6 require `pywin32` unconditionally. | Normal Mac dependency resolution fails before OK-WW installs. | Framework **Stage 2**, then repeat OK-WW editable install. |
| GAME-PKG-02 | `requirements.txt` | The generated lock contains `pywin32`, `pydirectinput`, `pycaw`, `comtypes`, `mouse`, and other Windows-resolved packages. | It is not a valid Mac installation manifest. | **Stage 2/7:** keep `pyproject.toml` authoritative and generate a Mac arm64 lock only after dependency markers are correct. |
| GAME-PKG-03 | `pyproject.toml` | `onnxocr-ppocrv5`, `openvino`, and `opencv-python` are declared, but full arm64 runtime/import behavior is not yet validated because resolution stops at `ok-script`. | Recognition and packaging capability remain unknown. | **Stage 6:** validate CPU correctness and arm64 native libraries; **Stage 7:** validate packaged resources. |
| GAME-PKG-04 | `pyproject.toml`, `config.py` | `pyappify` is a direct dependency and `update_pyappify` points at a Windows zip. | Windows launcher/update behavior can leak into Mac startup or packaging. | Framework **Stage 2** import isolation; OK-WW **Stage 6/7** explicit Mac disablement or replacement. |
| GAME-PKG-05 | OCR config | `use_openvino=True` and `use_npu=True` are global defaults. | Apple Silicon may attempt an unsupported NPU path or report misleading state. | **Stage 6:** use a proven CPU path and disable/safely ignore NPU on Darwin. |

No temporary wheel, `--no-deps`, mutable branch dependency, or copied framework package is permitted as a workaround.

## 3. Direct OS and concrete-backend coupling

| ID | Location | Current behavior | Why it matters | Required disposition |
|---|---|---|---|---|
| GAME-OS-01 | `src/combat/CombatCheck.py` | Imports `win32api` at module scope. `ensure_levitator()` reads and warps the global cursor and calls `capture.get_abs_cords(...)`. | Importing combat code fails on Mac even if the path is rarely used. It also couples task logic to HWND/global-screen semantics. | `ok-script` CursorService and geometry service in **Stage 5**; consume them here in **Stage 6**. Keep long-hold release paths protected with `try/finally`. |
| GAME-OS-02 | `src/task/MouseResetTask.py` | Imports `win32api`, reads/warps the cursor, and depends on `self.hwnd.exists`, `self.hwnd.visible`, and capture absolute coordinates. It continually reschedules itself. | This is both an import blocker and a Windows/background-window behavior, not a generic Mac requirement. | **Stage 6:** either implement through explicit framework cursor capabilities when real Mac evidence requires it, or disable/hide it on Mac P0 with observable state and tests. Do not add a `src.compat.win32api` shim. |
| GAME-OS-03 | `src/task/WWOneTimeTask.py` | Imports concrete `PostMessageInteraction` and calls `activate()` only when the interaction is that Windows class; it also imports/runs `MouseResetTask`. | Task import can trigger the broad Windows interaction export, and behavior is selected by concrete class identity rather than capability. | Framework import isolation in **Stage 2**; replace the concrete backend check with platform-neutral activation/capability behavior in **Stage 6**. |
| GAME-OS-04 | `src/task/ChangeEchoTask.py` | Uses `os.startfile(...)` to open the screenshots folder. | The successful-task path fails on macOS. | Add/use a platform-neutral framework open/reveal service; integrate in **Stage 6**. |
| GAME-OS-05 | `src/task/EnhanceEchoTask.py` | Uses `os.startfile(...)` to open the screenshots folder. | Same portability failure as GAME-OS-04. | Same **Stage 6** framework-service migration. |
| GAME-OS-06 | `config.py` registry helpers | Windows executable discovery uses `winreg`, but imports it inside functions and returns `None` when unavailable. | It is not currently a top-level Mac import blocker, but must remain reachable only from the Windows provider. | Preserve Windows behavior; add separate verified Mac app/window hints in **Stage 6**. Do not generalize registry logic. |
| GAME-OS-07 | `config.py` `windows` block | Declares Windows executable/class, PostMessage, WGC/BitBlt, HDR and Night Light settings. | These settings cannot be reused as a nominally generic desktop configuration. | Keep unchanged for Windows; add a separate `macos` provider configuration after framework Stage 3–5 gates. |
| GAME-OS-08 | `config.py` updater block | References `ok-ww-win32.zip`. | Cannot be offered as a Mac updater path. | Explicitly disable for source/Mac P0 and replace only after Stage 7 packaging design. |

The source scan found no direct AppKit, Quartz, ScreenCaptureKit, or ApplicationServices imports in OK-WW. That is the desired ownership boundary and must remain true.

## 4. Import and task-registration consequences

The application registers all built-in task modules through string paths. Mac import smoke must import every registered task, not only the first task used in a manual test.

Current blockers include:

- `MouseResetTask` itself fails at module import because of `win32api`;
- `WWOneTimeTask` imports both `MouseResetTask` and the concrete `PostMessageInteraction` type;
- combat/task inheritance chains can therefore fail before any device is selected;
- user-facing task code that only opens a folder can fail late because `os.startfile` is not available;
- task tests currently patch `src.task.MouseResetTask.win32api`, cementing the OS-shaped test seam.

Required import gate after Stage 2/6 work:

- import `config`;
- import the application/runtime entry;
- import every `onetime_tasks`, `trigger_tasks`, `scene`, `custom_tabs`, combat, and shared task base module;
- prove no `win32*` module is loaded on Darwin;
- preserve Windows task behavior and existing persisted configuration keys.

## 5. Windows-specific optional features and P0 disposition

| Feature | Current source | Mac P0 decision |
|---|---|---|
| Mouse-reset workaround | `MouseResetTask` | Explicitly unavailable unless real Mac testing demonstrates a need and framework CursorService can implement it safely. It must not block task imports. |
| PostMessage activation path | `WWOneTimeTask` | Replace concrete class checks with a provider capability. No PostMessage emulation on Mac. |
| Registry/UserAssist executable discovery | `config.py` | Windows-only and preserved. Mac uses observed application/window metadata. |
| WGC/BitBlt/PostMessage configuration | `config.py` | Windows-only and preserved. Mac gets its own provider block. |
| HDR/Night Light controls | Windows config/framework | Explicitly disabled/unavailable on Mac P0. |
| PyAppify launcher/update zip | dependency and `update_pyappify` | Must not block source bring-up; no Windows archive fallback on Mac. |
| Open screenshot folder | two task files | Use a platform-neutral open/reveal service. |
| Browser/emulator behavior | framework providers | Not a substitute for the native Mac MVP and not required for Mac parity. |

## 6. Recognition, visual, and task bring-up inventory

Current positive baseline:

- task coordinates and most input already use framework methods such as `click`, `send_key`, `send_key_down`, `send_key_up`, `next_frame`, and recognition helpers;
- there is no pre-emptive `assets/macos` tree;
- supported resolutions already include 1920×1080 and the planned follow-up 16:9 sizes.

Unknowns that remain `not-implemented` until evidence exists:

- content-area normalization from the official Mac client;
- BGR/color/gamma equivalence;
- template/OCR compatibility;
- CPU inference correctness and performance;
- hotkey equivalence in the official Mac client;
- task compatibility, including held-key/middle-button locked gameplay and any future free-camera route.

Updated bring-up order:

1. offline/diagnostic normalized frames;
2. simple `MAC_BASIC` menu/click/claim flow;
3. Auto Pick or another key-tap trigger;
4. held W/A/S/D, middle-button and button-hold combinations;
5. representative `MAC_LOCKED_GAMEPLAY` flow if those capabilities pass;
6. relative mouse only for tasks that explicitly require `MAC_FULL_CAMERA`;
7. broad task matrix.

Mac-specific assets are allowed only after reproducible same-resolution evidence shows that geometry/normalization/threshold changes would damage Windows recognition.

## 7. Tests and CI inventory

Stage 0 Mac baseline:

```text
Ran 38 tests
FAILED (errors=27)
```

The failures primarily reflect the blocked framework install, missing transitive dependencies, and direct Win32 imports. They are not evidence that 27 task algorithms are logically broken on Mac.

Specific test coupling:

- `tests/TestMouseResetTask.py` patches the module-level `win32api` object and must move to a platform-neutral cursor/capability fake;
- current `.github/workflows/test.yml` runs only on `windows-latest`, installs the Windows-generated `requirements.txt`, and invokes each unittest file independently;
- there is no required Mac import/discovery job;
- CI currently cannot distinguish Windows-only tests from platform-neutral tests.

Disposition:

- framework **Stage 2**: make normal dependency installation and shared imports possible;
- OK-WW **Stage 6**: update OS-coupled tests and add task compatibility/import tests;
- **Stage 7**: add a Python 3.12 macOS job that does not install the game, while keeping Windows CI green.

## 8. File-to-stage map

| File/area | Stage 2 | Stage 3 | Stage 4 | Stage 5 | Stage 6 | Stage 7 |
|---|---:|---:|---:|---:|---:|---:|
| Framework package markers/build metadata | X |  |  |  |  |  |
| Framework import/provider routing | X |  |  |  |  |  |
| `config.py` separate Mac provider hints |  | framework prerequisite | framework prerequisite | framework prerequisite | X |  |
| `CombatCheck.py` cursor use | import gate only |  | geometry prerequisite | CursorService prerequisite | X |  |
| `MouseResetTask.py` | import gate only |  |  | cursor prerequisite | X |  |
| `WWOneTimeTask.py` concrete backend check | framework export gate | activation capability prerequisite |  |  | X |  |
| `ChangeEchoTask.py`, `EnhanceEchoTask.py` |  |  |  | framework open/reveal service | X |  |
| OCR/NPU/visual/task compatibility |  |  | capture prerequisite | input prerequisite | X | packaged validation |
| Windows-only updater/launcher | import-safe disablement |  |  |  | config/documentation | X |
| macOS CI and `.app` |  |  |  |  |  | X |

## 9. Stage 1 exit assessment

- [x] Scope and prohibited mechanisms compared with framework constraints; no unresolved internal conflict found.
- [x] Direct OS calls and concrete Windows backend dependencies inventoried.
- [x] Windows-only optional features assigned an explicit Mac P0 disposition.
- [x] Dependency, recognition, task, test, and CI blockers mapped to Stages 2–7.
- [x] The initial capability matrix is recorded separately.
- [x] ADR and upstream sync/rollback procedures are established.
- [x] No runtime source, task behavior, asset, dependency metadata, or CI workflow changed in Stage 1.

The game-repository inventory is sufficient to begin Stage 2 framework packaging/import isolation without expanding product scope.
