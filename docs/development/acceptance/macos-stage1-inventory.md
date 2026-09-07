# OK-WW macOS Foreground MVP — Stage 1 Inventory Record

Status: **complete**

Recorded: 2026-09-04

Scope: guardrail confirmation, static implementation inventory, capability baseline, ADR process, and upstream sync/rollback procedure only

Stage 1 contains no dependency metadata implementation, provider routing, WindowTarget, ScreenCaptureKit, Quartz, task behavior, asset, CI, or packaging runtime change.

## 1. Repositories and scan points

| Repository | Pre-Stage-1 HEAD | Starting `upstream/master` | Ahead/behind upstream at scan |
|---|---|---|---|
| `ok-script` | `670ba36e148f954eb353f9c264920a33bf6229a7` | `784231e1c5f57a76baf5b4c2ccdef85bbe1d5766` | 1 ahead / 0 behind |
| `ok-wuthering-waves` | `988812769b2d1390555a2f4ece63bc6a7e84e8c4` | `a24c30f2ec90e56e40287bb76caf7c3a52266d77` | 1 ahead / 0 behind |

Both worktrees were clean before Stage 1. `origin` remains the contributor fork, `upstream` remains the canonical `ok-oldking` repository, and both branches are `feature/macos-foreground-mvp`.

## 2. Scope and conflict review

Compared documents:

- OK-WW `AGENTS.md`;
- `MACOS_ENGINEERING_CONSTRAINTS.md`;
- `docs/development/macos-foreground-port-plan.md`;
- `ok-script` `AGENTS.md`;
- `docs/development/macos-foreground-platform-constraints.md`;
- applicable task/i18n/virtual-environment instructions.

Conclusion:

- no unresolved internal conflict exists among the committed contributor-branch rules;
- foreground-only, public-API-only, fail-closed, repository-ownership, and Windows-regression boundaries are consistent;
- Stage 2 can begin without changing product scope;
- this conclusion does not claim that upstream maintainers have already accepted the design; final upstream acceptance remains a final-PR gate.

Implementation choices such as the exact deterministic versioning mechanism, final module layout, or Mac P0 hotkey/notifier UI are still open, but they must remain inside the existing constraints. They are not unresolved product-boundary conflicts.

## 3. Framework inventory outcome

Detailed record:

```text
ok-script/docs/development/macos-stage1-platform-inventory.md
```

Primary findings:

- editable metadata evaluation is blocked by undeclared `get_pypi_latest_version` usage in `setup.py`;
- `pywin32`, `pydirectinput`, `pycaw`, and `mouse` are unconditional dependencies; `comtypes` is pulled transitively;
- `pynput`, PyAppify, and Windows desktop-duplication dependencies are wider than the core Mac MVP requires;
- `DeviceManager`, capture and interaction aggregate exports, shared key/types files, `ok.util.window`, generic startup, Qt startup, notifications, browser capture, and optional tools pull Windows implementations before platform selection;
- the normal Qt start chain imports `StartCard` and `DebugTab`, both of which load Win32 global-hotkey primitives at module scope;
- existing Windows-only capture/input/overlay/notification/emulator implementations should remain Windows-specific and be hidden behind lazy provider boundaries rather than rewritten;
- no platform-neutral desktop target, Mac provider, permission service, ScreenCaptureKit stream, Quartz backend, geometry generation, cursor service, held-state gate, or `release_all()` contract exists yet;
- current framework tests and workflow coverage do not provide the required Darwin import/provider gates.

All findings are assigned to Stages 2–7.

## 4. Game-repository inventory outcome

Detailed record:

```text
docs/development/macos-stage1-game-inventory.md
```

Primary findings:

- normal OK-WW installation is blocked by the published framework's unconditional `pywin32` dependency;
- the current generated `requirements.txt` is Windows-resolved and is not a Mac install manifest;
- `src/combat/CombatCheck.py` and `src/task/MouseResetTask.py` directly import/use `win32api`;
- `src/task/WWOneTimeTask.py` imports and checks concrete `PostMessageInteraction` and imports the Windows-oriented mouse-reset task;
- `ChangeEchoTask.py` and `EnhanceEchoTask.py` use `os.startfile`;
- Windows registry discovery is already function-local and may remain Windows-only, but the game requires a separate verified Mac provider configuration;
- global `use_npu=True` and the Windows PyAppify update archive require explicit Mac behavior;
- all registered tasks must be included in the Darwin import gate, not only tasks selected for early manual bring-up;
- no direct AppKit, Quartz, ScreenCaptureKit, or ApplicationServices import exists in OK-WW, and that ownership boundary must be preserved;
- the existing Windows-only CI job and OS-shaped tests require later platform separation.

## 5. Initial capability state

Detailed matrix:

```text
docs/development/macos-capability-matrix.md
```

Every macOS runtime capability is currently `not-implemented`, including:

- install/build/import/provider routing;
- desktop target and permissions;
- selected-window capture and geometry;
- Quartz input, held state, focus guard, and cursor service;
- game matching, inference, recognition, and task flows;
- macOS CI and packaged application behavior.

Stage 0 and Stage 1 completion is process/documentation evidence only and does not advance a runtime capability.

## 6. Decision process

Both repositories now contain:

```text
docs/development/decisions/README.md
docs/development/decisions/0000-template.md
```

An ADR is required for a deliberate normative deviation, cross-repository contract change, security/permission assumption, incompatible Windows change, substantial external-code adoption, or materially different capture/input/package architecture.

A proposed ADR does not authorize violating code. The relevant project owners/maintainers must accept it before implementation proceeds.

## 7. Sync and rollback process

Both repositories now contain:

```text
docs/development/macos-integration-sync-and-rollback.md
```

The procedure establishes:

- clean-worktree and remote-identity preflight;
- local recovery refs before upstream integration;
- normal merge as the default for published long-lived branches;
- rebase only when unshared or explicitly coordinated, using `--force-with-lease` if required;
- cross-repository validation order;
- abort/reset behavior before push and revert behavior after push;
- consumer-first guarding for cross-repository incompatibility;
- immediate capability downgrade and fail-closed rollback for safety regressions;
- evidence invalidation after relevant upstream or implementation changes.

## 8. Stage 2 entry order

Stage 2 should begin in `ok-script` in this order:

1. make isolated/editable build metadata deterministic;
2. add platform markers/optional boundaries for Windows-only dependencies while preserving Windows defaults;
3. separate common capture/interaction/key/type exports from concrete Windows modules;
4. make `DeviceManager` and `OK` startup select providers before loading implementations;
5. make Qt startup and notification imports safe on Darwin, explicitly disabling unsupported P0 tools;
6. add Mac clean-environment install/import tests and Windows regression tests;
7. rerun the OK-WW normal editable install and full registered-module import discovery.

Stage 2 must not add production ScreenCaptureKit, Quartz event posting, game matching, task compatibility logic, or Mac assets.

## 9. Stage 1 exit checklist

- [x] Both repositories were synchronized/fetched and had no new upstream commits behind the integration branches.
- [x] Scope and forbidden mechanisms were compared; no unresolved internal rule conflict remains.
- [x] `ok-script` dependency and import blockers are mapped to files and stages.
- [x] Windows-only implementations are distinguished from shared import blockers.
- [x] OK-WW direct OS calls, concrete backend checks, and optional Windows features are mapped to files and stages.
- [x] Initial capability matrix exists and makes no unsupported runtime claim.
- [x] ADR policy and template exist in both repositories.
- [x] Upstream sync and rollback procedures exist in both repositories.
- [x] Stage 2 minimum boundary and entry order are explicit.
- [x] No runtime code, dependency metadata, task behavior, asset, CI, lock file, or packaging configuration changed.
- [x] Stage 1 documentation commits are pushed to both contributor-fork integration branches.
- [x] No incremental/foundation PR is opened.
- [x] Both worktrees are clean after the commits.

Stage 1 is complete. The next permitted work is Stage 2 platform-safe packaging, imports, and provider selection. No macOS runtime support is claimed by this record.
