# Agent Instructions

## Scope

This repository is adding a **macOS foreground-only** port of OK-WW.

Before changing any macOS-related code, read:

- `MACOS_ENGINEERING_CONSTRAINTS.md`
- `docs/development/macos-foreground-port-plan.md`
- `docs/development/macos-stage1-game-inventory.md`
- `docs/development/macos-capability-matrix.md`
- `docs/development/macos-integration-sync-and-rollback.md`
- `docs/development/decisions/README.md`
- existing task skills under `.agents/skills/`, especially `ok-script-tasks` and `ok-script-i18n`

The macOS MVP is intentionally narrow. Do not expand its scope without an explicit design decision.

## Instruction Precedence and Change Control

- `MACOS_ENGINEERING_CONSTRAINTS.md` is the normative product and engineering contract for the macOS foreground MVP.
- `docs/development/macos-foreground-port-plan.md` describes the implementation sequence and may not weaken the normative constraints.
- Repository-local `AGENTS.md` files and advertised skills apply in addition to these rules. A more specific instruction may refine implementation details, but it must not relax the foreground-only or fail-closed safety requirements.
- Resolve instruction conflicts before changing runtime code. Safety, public-API-only operation, repository ownership boundaries, and Windows compatibility take precedence over implementation convenience.
- Any deliberate deviation requires a committed architecture decision record under `docs/development/decisions/` that documents the reason, considered alternatives, security and permission impact, Windows regression impact, test plan, migration path, and rollback plan. A code comment or PR discussion alone is not sufficient.

## Workspace and Repository Identity

Use sibling checkouts during development:

```text
workspace/
├── okww-macos-foreground-plan/   # planning and sanitized acceptance evidence
├── ok-script/                    # reusable platform implementation
└── ok-wuthering-waves/           # this game-specific integration repository
```

The planning directory may contain only constraints, plans, checklists, and sanitized acceptance records. Production game integration belongs in this repository; reusable platform code belongs in `ok-script`.

For each source repository:

- `origin` must identify the contributor fork used to publish the integration branch.
- `upstream` must identify the canonical `ok-oldking` repository.
- Create `feature/macos-foreground-mvp` from the current `upstream/master`, not from an unrelated local branch.
- Record the initial upstream commit SHA before runtime work begins.
- Keep the two source repositories as independent Git repositories. Do not add one as a submodule, subtree, copied package, or vendored directory of the other.
- Before editing, inspect that repository's own `AGENTS.md`, nested instruction files, and applicable skills.
- Never commit local absolute paths, credentials, signing identities, notarization secrets, TCC database material, personal screenshots, logs containing account data, virtual environments, app bundles, DMGs, or generated build directories.

## Development Branch and Pull Request Policy

The macOS MVP is developed on a dedicated long-lived integration branch, not through a sequence of partial pull requests.

- Use a dedicated branch such as `feature/macos-foreground-mvp`.
- Because reusable platform work belongs in `ok-script`, keep a matching integration branch in both affected repositories when both are being changed.
- During development, install the sibling `ok-script` checkout in editable mode. Do not publish temporary packages merely to connect the two branches.
- Keep commits small, buildable where practical, and logically scoped so regressions can be bisected. Small commits do not imply small PRs.
- Do not open incremental, placeholder, draft-for-merging, or “foundation only” PRs for the MVP.
- Rebase or merge current upstream changes into the integration branch regularly enough to expose conflicts before final acceptance.
- Do not merge incomplete Mac support into a default branch to unblock later work.
- Record automated and real-hardware acceptance results on the integration branch.
- Open the MVP PR only after all applicable acceptance gates in this file and `MACOS_ENGINEERING_CONSTRAINTS.md` pass.

A GitHub pull request cannot span repositories. Therefore, when both repositories change, the final delivery is **one cohesive MVP PR per affected repository**, coordinated as one release unit rather than split into topic PRs:

1. the `ok-script` MVP PR contains the reusable platform implementation;
2. the `ok-wuthering-waves` MVP PR contains the game integration and consumes an immutable compatible `ok-script` version or commit accepted by the maintainers.

The final OK-WW PR must not depend on a mutable branch URL. Local editable installs are development-only.

Each final MVP PR description must include:

- architecture summary and scope boundary;
- linked companion PR, when another repository is affected;
- automated test commands and results on Windows and macOS;
- real-hardware acceptance matrix and machine/macOS details;
- packaged-app permission validation results;
- known limitations and unsupported features;
- migration, rollback, and dependency-version notes.

### Stage 0 Bootstrap Gate

Do not begin runtime implementation until the following bootstrap facts are established and recorded:

- authenticated access to contributor forks for both `ok-script` and `ok-wuthering-waves`;
- sibling local checkouts with verified `origin` and `upstream` remotes;
- matching `feature/macos-foreground-mvp` branches based on recorded `upstream/master` SHAs;
- a clean worktree before the first implementation commit;
- Apple Silicon host verification and a macOS version within the supported baseline;
- an arm64 Python 3.12 interpreter and a repository-local `.venv` for OK-WW development;
- the sibling `ok-script` checkout selected for editable development rather than a mutable branch URL or temporary package publication;
- the normative constraints and implementation plan copied into this integration branch before platform code is expanded;
- baseline install/import/test commands and their results recorded, including expected failures caused by the pre-port Windows-only dependency graph;
- `.gitignore` coverage or equivalent checks preventing local environments, build artifacts, permission data, credentials, and private acceptance evidence from being committed.

A baseline failure is not permission to bypass the gate. Record it, associate it with the stage that must fix it, and keep later claims scoped to the gates that have actually passed.

## Python Environment

- When running Python commands in this repository, use the local virtual environment if it exists.
- On Windows/PowerShell, prefer `.\\.venv\\Scripts\\python.exe`.
- On POSIX shells, including macOS, prefer `./.venv/bin/python`.
- Fall back to `python` only when no local `.venv` interpreter exists.
- Prefer invoking the interpreter directly, for example:
  - Windows: `.\\.venv\\Scripts\\python.exe -m pytest`
  - macOS/Linux: `./.venv/bin/python -m pytest`
- Do not rely on shell activation when a direct interpreter path is available.
- The macOS reference development interpreter is Python 3.12 arm64.

## Repository Boundary: `ok-script` vs `ok-wuthering-waves`

Generic platform capability belongs in `ok-script`. Game-specific behavior belongs in this repository.

Put these in `ok-script`:

- macOS window/process discovery abstractions
- ScreenCaptureKit capture implementation
- Quartz foreground keyboard/mouse implementation
- foreground/focus guard
- held-input state and idempotent `release_all()`
- cursor service
- permission checks
- `DeviceCapabilities` and generic capability gates
- platform-neutral device routing
- platform-conditional dependency/import logic

Put these in `ok-wuthering-waves`:

- Wuthering Waves macOS app/window matching configuration
- game hotkey mapping choices
- Mac-specific asset overrides, if actually required by visual differences
- task-level capability requirements and `validated` / `experimental` / `unsupported` status
- replacement of the two current direct `win32api` usages with framework services
- user-facing documentation specific to OK-WW

Do not duplicate a macOS capture/input backend inside OK-WW just to avoid changing `ok-script`.
Do not add an OK-WW-local `win32api`-shaped compatibility shim; use platform-neutral framework services instead.

## macOS MVP Invariants

The first macOS version is **foreground only**.

当前 contributor 集成分支的 packaged MVP 最低版本为 macOS 15.0。`ok-script` 的公开 API 设计与通用 host gate 仍以 macOS 13+ 为基线；它们不构成 OK-WW 二进制对 13/14 的支持承诺。本决定经用户授权，不代表 upstream 已接受；不得通过下调 plist 或 Mach-O 标记伪造兼容性。

It MUST:

- run only on Apple Silicon
- target macOS 15 or newer for the current packaged OK-WW MVP; see `docs/development/decisions/0003-macos-packaged-minimum-version.md`
- use the official Wuthering Waves Mac client
- use public Apple APIs only
- capture the selected game window with ScreenCaptureKit
- send input only while the target game process is the frontmost application
- release every synthetic key/button immediately if focus is lost, the task stops, capture fails fatally, or the app exits
- pause/stop automation on focus loss instead of silently redirecting input
- preserve the existing Windows behavior

It MUST NOT add or use, for this MVP:

- BetterDisplay or any virtual-display dependency
- private `CGVirtualDisplay` APIs
- `CGEvent.postToPid` as a background-control mechanism
- game-process injection, dylib injection, swizzling, Metal hooks, or anti-cheat bypasses
- Android emulator support as a substitute for the native Mac MVP
- a fallback that sends global input when the game is not frontmost
- automatic TCC database modification or permission bypasses

## Platform Import Rules

Platform-neutral modules must be importable on both Windows and macOS.

- No unconditional `win32api`, `win32con`, `win32gui`, `win32process`, `winreg`, `ctypes.windll`, or `ctypes.WinDLL` imports in shared modules.
- No unconditional AppKit, Quartz, ScreenCaptureKit, or PyObjC imports in shared modules.
- Put platform implementations in platform-specific modules and import them lazily or behind `sys.platform` checks.
- Use environment markers in package metadata for platform-specific dependencies.
- Do not make task modules import OS APIs directly.

A basic import smoke test on macOS must be able to import the application, task executor, task modules, and device abstractions without loading Win32-only modules.

## Device and Interaction Rules

Task code should use the existing task/framework APIs rather than direct device access:

- frames and waits: `next_frame`, `wait_until`, `sleep`
- input: `click`, `click_relative`, `send_key`, `send_key_down`, `send_key_up`
- recognition: existing feature/OCR helpers

For new platform services:

- capture coordinates are frame-local physical pixels
- platform coordinate conversion happens only in the platform backend
- key/button down state must be tracked explicitly
- `release_all()` must be idempotent and safe to call repeatedly
- input functions must check the foreground guard immediately before posting an event
- tasks must declare precise capabilities and be rejected before execution when the active provider cannot satisfy them
- `relative_mouse=False` must not block a task that only requires basic or locked-gameplay input
- do not use a stale frame after a capture/window recreation failure

## ScreenCaptureKit Rules

- Use a persistent `SCStream` for continuous automation capture; do not create `SCScreenshotManager` requests for every automation frame.
- Prefer `SCContentFilter(desktopIndependentWindow:)` for the selected game window.
- Deliver the newest complete frame; do not build an unbounded frame queue.
- Normalize output to the framework contract: BGR `numpy.ndarray`, `uint8`, shape `(height, width, 3)`.
- Cursor must not be included in capture frames.
- Capture lifecycle must handle window recreation, resize, display-scale changes, and app exit.
- Screen Recording permission failure must produce an explicit actionable state, not an endless retry loop.

## Quartz Foreground Input Rules

- Use Core Graphics Quartz events for the production macOS foreground input backend.
- Do not make `pynput` the architectural abstraction; it may be used only as an isolated diagnostic/prototype.
- Support key down/up separately; many OK-WW combat paths depend on held keys.
- Support left/right/middle mouse buttons.
- Support absolute movement for the basic MVP. Implement and validate relative/delta movement as a separate `relative_mouse` capability for tasks that truly need free-camera control.
- Do not make `relative_mouse` a global MVP gate. `MAC_BASIC` and hardware-validated `MAC_LOCKED_GAMEPLAY` tasks may ship without it.
- Do not claim `MAC_FULL_CAMERA`, free-camera routes, complete route parity, or complete Windows parity until relative/delta movement passes real-game hardware validation.
- The game must be frontmost before every input batch/event.
- A task may request activation once at startup and must observe the game becoming frontmost; the input backend must never reactivate the game before every event.

## macOS Task Capability Model

Use two independent axes:

1. provider capability evidence: `not-implemented`, `unit-tested`, `hardware-validated`, `packaged-app-validated`;
2. task status: `validated`, `experimental`, `unsupported`.

Task risk levels are:

- `MAC_BASIC`: menu, login, claim, backpack, enhancement, fixed-page OCR/template and fixed-coordinate input;
- `MAC_LOCKED_GAMEPLAY`: held W/A/S/D, middle-button lock/center, left/right holds and keyboard/mouse combinations, without requiring arbitrary camera delta;
- `MAC_FULL_CAMERA`: free relative X/Y camera movement and precise route steering.

Every registered task must have an explicit declaration. Do not enable all tasks merely because the operating system is macOS. Unknown or undeclared tasks fail closed. An experimental task may be used for hardware acceptance, but must not be described as supported.

Current OK-WW code uses `center_camera()` as a middle-button action and contains no registered task call to free-camera delta. Validate actual held-key/middle-button combinations before investing in general relative movement.

## Permissions

The macOS app needs user-granted permissions; never bypass them.

At minimum design for:

- Screen & System Audio Recording / screen capture permission
- Accessibility permission for synthetic control

Use supported preflight/request APIs where available and show clear UI guidance. Do not edit the TCC database.

Development permission state attached to Terminal/Python is not equivalent to the final signed `.app`; final acceptance must use the packaged app identity.

## Visual and Resolution Rules

- Preserve the existing 16:9 task coordinate model.
- The first hardware acceptance resolution is 1920×1080.
- 1280×720, 1600×900, and 2560×1440 are follow-up compatibility targets matching the existing project configuration.
- Do not duplicate all templates for macOS preemptively.
- Add `assets/macos` overrides only when a reproducible visual difference requires them.
- Keep recognition logic platform-neutral.

## OCR / Inference Rules

- macOS uses CPU inference for the initial port.
- Do not require Intel NPU/GPU OpenVINO plugins on Apple Silicon.
- Any `use_npu` configuration must be disabled or safely ignored on macOS.
- Recognition correctness takes priority over premature inference optimization.

## Testing and Regression Rules

Every platform-layer change must preserve Windows behavior.

Required before opening the final macOS MVP PR:

1. Windows unit/import tests remain green.
2. macOS import tests pass without Win32 dependencies.
3. platform contract tests cover capture and interaction base behavior.
4. focus-loss tests verify `release_all()` and no further input.
5. coordinate conversion tests cover Retina/non-Retina scale assumptions.
6. real-hardware smoke results are recorded for the official Wuthering Waves Mac client before a feature is declared supported.

CI must not require the game to be installed.

## Generated Dependency Files

- `pyproject.toml` is the dependency source of truth.
- Do not hand-edit generated pip-compile lock output except for an emergency explicitly requested by the user.
- Prefer a dedicated macOS arm64 lock file during the port if one cross-platform generated file cannot remain reproducible.
- Keep Python 3.12 as the reference lock-generation version for this work.

## Packaging

Do not block platform bring-up on the current Windows PyAppify installer.

For the Mac port:

- source/dev execution comes first on the integration branch
- create a stable-bundle-identifier internal `.app` as soon as window and permission boundaries exist; do not postpone TCC identity testing until every task is complete
- validate launch from `/Applications`, permission persistence across restart/rebuild, and explicit behavior after revocation
- do not run from inside a DMG as the standard acceptance path
- ad-hoc signing is not public-release evidence
- packaged `.app` validation is required before opening the final MVP PR; Developer ID notarization remains a public-release gate
- prefer the supported PySide deployment path (`pyside6-deploy` / Nuitka) unless testing proves another path is required
- public distribution must use a stable bundle identifier, Developer ID signing, Hardened Runtime, timestamp, notarization, and staple
- do not add private APIs to the foreground MVP

## Safety / Failure Behavior

Fail closed.

If any of these conditions occurs, stop posting input and release held state:

- game is no longer frontmost
- target process/window disappears
- capture stream fails and cannot be recovered
- frame geometry becomes invalid
- permission is revoked
- task/executor/app is stopping

Never “best effort” by sending global input to whatever app is currently active.

## MaaEnd / MaaFramework Reference Boundary

MaaEnd and MaaFramework may be read as evidence that ScreenCaptureKit window capture and Quartz CGEvent input are feasible. They are references, not runtime dependencies.

Do not copy their per-request screenshot path, use `SCWindow.frame` as content pixel size, reactivate the target before every input, or treat a background controller as proof that this branch may add background support. Adding MaaFramework binaries or dylibs requires a separate ADR and is outside this MVP.

## Documentation Language and Claims

New or modified macOS engineering constraints, implementation plans, and acceptance records use Chinese by default. Keep API names, class names, function names, paths, configuration keys, log state codes, and commands in English.

Every status report must separate completed automated evidence from real-game and packaged-app evidence. Never label an unperformed real-game test as supported.
