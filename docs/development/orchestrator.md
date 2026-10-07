# Orchestrator (draft)

This opt-in page uses the project's existing Qt / QFluentWidgets / ConfigCard
components. It does not copy another assistant's UI or replace Daily Task.

## Usage

1. Open **Orchestrator** in the sidebar.
2. Click **Add**, select a step, and add it to the queue.
3. Drag rows to reorder. Click a row to edit its native parameters.
4. Select a row and click **Remove selected** to remove it entirely.
5. Click **Start plan**. Pause / Stop use the existing task executor.

Example: Open game → Nightmare Nest → Farm natural stamina → Claim daily
rewards → Claim mail → Close game → Wait → Exit assistant.

The app-wide automatic game startup preference remains unchanged. Disable it
manually if opening the game should be controlled only by this queue.

## Behavior and limitations

- The initial plan is empty. Existing task configs and CLI indices are not migrated.
- Business tasks occur once; control steps have unique IDs and can repeat.
- Exit assistant must be last. It does not implicitly close the game.
- Close game verifies the selected executable path/PID identity before terminating
  it, then waits for exit. This is termination, not an in-game graceful quit.
  Unknown target or timeout is reported as failure, never a name-wide kill.
- Wait needs no capture and pauses its countdown while paused.
- A login/required step failure remains an overall failure, even when cleanup
  succeeds. Optional failures remain visible. Stop cancels the remaining queue.
- Tasks are not blindly retried: a resource operation may have succeeded before
  a subsequent navigation/read failed.
- Farm natural stamina reuses the configured native farming functions and the
  helper proposed in #1729. It does not use reserve, recharge or purchases.
- Claim daily rewards runs exactly where placed; it is not secretly repeated
  after farming. Successful native execution is **not** independently verified
  proof that the highest activity reward was claimed.
- Nightmare Nest has Daily / All modes in one step, not two duplicate tasks.
- Boss Echo farming copies native settings and bounds repeats to 1–100, then
  restores the original config even on failure/cancellation.
- Weekly stamina rewards, personal reward-recognition assets, accelerator
  connections, graphics profiles, and reserve top-up are outside this PR.

## Development checks

The draft requires the paired frame-independent executor change in ok-script.
The current dependency pins intentionally remain unchanged until that change
is reviewed, released, and a supported version can be selected.

Run with the project's virtual-environment Python:

    python -m unittest discover -s tests -p "test_orchestrator*.py" -v
    python tests/orchestrator_ui_probe.py --framework /path/to/ok-script

The Qt probe uses temporary configs and an offscreen window; no game launches.
It exercises loading, Add picker, native drag/drop, parameter reset/persistence,
repeated Wait, terminal Exit guard, editing locks, queuing, pause, and stop.
Offline checks are not live game verification. Full live end-to-end validation,
maintainer direction, translations, and dependency integration are still
required before this draft is ready to merge.
