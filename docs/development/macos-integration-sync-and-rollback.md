# OK-WW macOS Foreground MVP — Upstream Sync and Rollback Procedure

Status: **required integration workflow**

Applies to: the coordinated `ok-script` and `ok-wuthering-waves` integration branches

## 1. Principles

- Each repository develops on the published long-lived `feature/macos-foreground-mvp` branch.
- `origin` is the contributor fork and `upstream` is the canonical `ok-oldking` repository.
- The repositories remain independent but are tested and delivered as one release unit.
- Preserve published history; routine sync must not force-push a shared branch.
- Sync and rollback may not weaken foreground-only, public-API-only, fail-closed behavior or Windows compatibility.
- A relevant upstream change or regression reopens affected evidence gates.

## 2. Sync cadence

Sync both repositories:

- before each implementation stage;
- when upstream changes an inventoried file or dependency;
- before real-hardware testing;
- before packaged-app testing;
- immediately before final acceptance freeze and PR creation.

Each acceptance record identifies both repository SHAs. Do not validate OK-WW against an unrecorded sibling framework state.

## 3. Pre-sync checks

Run in both repositories:

```bash
git status --short --branch
git remote -v
git fetch --prune origin
git fetch --prune upstream
git rev-list --left-right --count HEAD...upstream/master
```

Confirm:

- worktree and existing submodules are clean;
- current branch is `feature/macos-foreground-mvp`;
- branch tracks `origin/feature/macos-foreground-mvp`;
- `origin` and `upstream` identify the expected repositories;
- no generated lock/build artifact or private evidence is pending.

Create a local recovery ref in each repository:

```bash
git branch backup/macos-foreground-pre-sync-YYYYMMDD-HHMM HEAD
```

Record pre-sync HEAD, upstream SHA, companion SHA, backup ref, current stage, and known-green tests.

## 4. Default sync procedure

The integration branches are published, so the default is a normal upstream merge:

```bash
git switch feature/macos-foreground-mvp
git merge --no-edit upstream/master
```

When conflicts occur:

1. do not discard platform guards, safety release paths, or existing Windows behavior for convenience;
2. compare the upstream intent with the Stage 1 inventories;
3. limit resolution to the actual conflicting behavior;
4. update the inventory or create an ADR for an architectural conflict;
5. run `git diff --check` and stage-specific tests before pushing.

A rebase is allowed only before sharing or with explicit collaborator coordination. Rewritten pushes use `--force-with-lease`, never plain `--force`; rebase is not the routine long-lived-branch workflow.

Recommended order:

1. sync `ok-script`;
2. run framework/import/Windows tests appropriate to the stage;
3. refresh the OK-WW sibling editable install;
4. sync OK-WW;
5. run OK-WW import/task tests;
6. run any cross-repository contract tests;
7. push both branches after review.

## 5. Post-sync development validation

After Stage 2 begins, the minimum Mac commands from the OK-WW checkout are:

```bash
./.venv/bin/python -m pip install -e "../ok-script[ocr,qt]"
./.venv/bin/python -m pip install -e ".[dev]"
./.venv/bin/python -c "import ok"
./.venv/bin/python -c "from ok.device.DeviceManager import DeviceManager"
```

Also run:

- Windows regression tests/CI for every changed framework path;
- Darwin provider and import-isolation tests;
- every registered OK-WW task/module import;
- current-stage unit/contract tests;
- any hardware or packaged-app checks invalidated by the sync.

Do not carry forward old acceptance evidence after a relevant implementation, dependency, geometry, capture, input, permission, or bundle-identity change.

Push normally:

```bash
git push origin feature/macos-foreground-mvp
```

Do not open a stage or foundation PR during routine sync.

## 6. Rollback before push

For an unresolved, uncommitted integration:

```bash
git merge --abort
# or, only when an explicitly coordinated rebase was used:
git rebase --abort
```

For local commits not yet shared, after confirming there is no wanted uncommitted work:

```bash
git reset --hard backup/macos-foreground-pre-sync-YYYYMMDD-HHMM
```

`reset --hard` is permitted only against the recorded local backup and before history is shared.

## 7. Rollback after push

Never rewrite shared history as the normal rollback. Revert it:

```bash
git revert <commit>
git revert -m 1 <merge-commit>
```

Run the same tests required for the original change before pushing the revert.

For a cross-repository incompatibility:

1. first stop, guard, or revert the OK-WW consumer path so it cannot call an incompatible/unsafe framework capability;
2. revert or repair the framework implementation;
3. reinstall the sibling editable framework and rerun imports/contracts;
4. update the final immutable dependency note;
5. reopen every dependent capability gate.

Never use a mutable branch URL, undeclared local patch, copied package, or temporary wheel as rollback state.

## 8. Safety-critical rollback

When a regression could leak input, leave state held, use stale frames/coordinates, bypass permission, or continue when another app is frontmost:

1. mark the capability unsupported immediately;
2. block all new ordinary input;
3. keep `release_all()` best-effort and reachable;
4. revert the unsafe change before continuing feature work;
5. rerun focus-loss, target-loss, capture-loss, permission-loss, and shutdown tests;
6. invalidate dependent hardware and packaged-app evidence.

Rollback must fail closed. It may not restore global-input fallback, `CGEvent.postToPid`, private API, virtual display, injection, or TCC bypass behavior.

## 9. Rollback expectations by change type

| Change type | Required rollback note |
|---|---|
| Dependency markers/build metadata | Previous resolvable Windows dependency behavior, regenerated lock implications, and Mac install effect. |
| Import/provider routing | Legacy import compatibility and how Windows/ADB/browser providers return to the prior path. |
| Desktop target/capture/input contract | Adapter/version boundary, configuration compatibility, and safety state during rollback. |
| OK-WW config/task behavior | Persisted config keys, task visibility/defaults, user-facing capability status, and asset fallback. |
| Packaged application | Bundle identifier, permission reset implications, signing/notarization state, and user data/config preservation. |

## 10. Final PR preparation

Before opening final PRs:

- sync both repositories and record exact SHAs;
- verify both worktrees and submodules are clean;
- verify each integration branch tracks its contributor-fork origin branch;
- record the immutable accepted `ok-script` revision/version consumed by OK-WW;
- remove distributable dependence on sibling/local paths;
- include migration, rollback, Windows regression, permissions, and known-limitations notes;
- link the two final PRs as one coordinated MVP delivery.
