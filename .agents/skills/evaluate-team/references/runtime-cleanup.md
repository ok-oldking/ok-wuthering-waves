# Runtime refresh and diagnostic cleanup

Read this for character instrumentation, version switching, or retaining a
candidate. Reuse the current project's verified MCP runtime; restarting a short
SDK client is not an OK-WW restart.

## Stop first when testing is stopped

A batch driver can submit another run after the current attempt ends. Stop that
owned driver and request `stop_task(run_id)` for the active MCP attempt. Read the
terminal status and allow its `finally`/`ExitStack` cleanup to finish. A terminal
failed/cancelled run does not need another combat to be stopped. Do not terminate
unrelated Python processes or replace the user's GUI.

"Don't test" means no more combat or offline test runs unless the user later
changes that instruction. Retaining code may still require file edits, cache
refresh, and source/binding inspection. Keep those operations application-only:
no `restart_combat_in_abyss()`, attack input, stage recovery, or performance probe.
The evaluator's `reset_to_start()` starts combat, so do not reuse or subclass that
entry point merely to install a candidate or check cleanup.

If a live challenge needs attention, stop automation/release held inputs and
report its state. Do not start another fight to leave a convenient result screen.

## Refresh the actual character implementation

For character-only changes, prefer the existing custom-team loader under MCP
executor ownership between combats. Clear the relevant cache with
`clear_team_char_cache(team, character)`, then reapply classes through normal
`load_chars()` when the party is visible. Preserve existing custom/imported team
code rather than replacing it with a built-in copy. Recreate per-character combat
caches consistently on measured arena resets.

For cleanup-only application when portraits are hidden, use the loader's existing
class-application path on a known cached roster or defer fresh recognition to
the next normal load. Do not recover an arena just to inspect portraits. State
whether code was applied to cached instances or will take effect on next load.

Check these details when a refresh appears to use old code:

- An identical team file can trigger the loader's built-in shortcut. Matching
  disk files does not prove the imported built-in class was refreshed. Ensure a
  retained functional team override selects the intended class, or use a coherent
  supported dependency refresh/restart when necessary.
- Dynamically loaded modules may not be in `sys.modules`; `inspect.getfile(cls)`
  can fail. Use a defining method's `__code__.co_filename` as the source fallback,
  and record source hash/module identity rather than relying on the class name.
- Class replacement can copy the old instance dictionary. Exit diagnostic scopes
  before replacing classes; inspect instance-bound method overrides as well as
  the new class. Remove only known diagnostic wrappers/restored bindings, keeping
  intentional user overrides intact. A new class label alone is insufficient.
- After template export, refresh `self.executor.feature_set.process_data()` under
  executor ownership once capture dimensions are available. The library's
  generate-templates skill documents this. Keep existing feature pixels intact;
  do not restart the application merely to refresh assets.

`reload_tasks()` refreshes registered tasks, not all cached built-in characters,
`BaseChar`, `CharFactory`, or combat helpers. Group necessary shared dependency
changes before a restart. Avoid a generic `importlib.reload()` that leaves old
class references and instances behind.

## Retain and clean up

Identify the selected version by its saved source, not by whichever control or
candidate happened to run last. Preserve that functional implementation in the
actual team override and built-in source where appropriate. Re-read files before
writing if the user may have edited them while the run was active. Never restore
the whole tree to Git HEAD to remove instrumentation.

Remove evaluation-only logging, screenshots-in-code, counters used only for those
diagnostics, and temporary wrappers/settings from both source and live instances.
Preserve functional templates, regression fixtures, unrelated logging, and user
changes. Archive experimental harnesses, rejected variants, metrics, and screenshots
with the report; they should not remain production implementations.

Report retained source/override, effective loaded class, cleanup performed, and
remaining uncertainty. Separate tests completed before cleanup from any final
source/binding inspection. When the user stopped tests, do not imply that the
cleaned source was retested or that a successful class application proves combat
behavior or performance.
