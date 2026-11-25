---
name: ok-script-develop
description: Develop or modify game automation functions using ok-script MCP, including tasks, characters, combat helpers, navigation, and recognition. Load the library's own development skills from the linked ok folder first, then the application's installed site-packages.
---

# Game Development with OK Script

Use the library's current consumer-application skills as the basis for development.
This skill adds discovery and project integration; the library supplies the task
contract, MCP workflow, and validation instructions. Work in the consuming
application and use its local virtual environment.

## Locate the library instructions first

Resolve skills in this order before editing game behavior:

1. Check `<cwd>/ok`. If present, resolve its symlink or junction target. For a
   source checkout, look in `<resolved-ok>/../.agents/skills`; for a packaged
   directory, look in `<resolved-ok>/agent_resources/.agents/skills`.
2. If the linked/local directory does not provide the relevant consumer skills,
   locate the application's installed `ok-script` distribution using its Python
   interpreter and `importlib.metadata.distribution('ok-script').locate_file(...)`.
   Look under `ok/agent_resources/.agents/skills` in that environment's
   `site-packages`. Do not use a different interpreter's global installation.
3. Read `develop/SKILL.md` from the selected library. Resolve its relative links
   from that file, including `docs/mcp.md`. Read `reload-tasks` for existing tasks,
   `write-test` for tests, and `generate-templates` for visual assets. Read setup
   skills only when environment or runtime setup is needed.

The library's `ok/core/skills.py` implements its source/package discovery. When
available, run that file with `runpy.run_path` and call its `list_skills()` or
`get_skill()` functions without importing the GUI runtime just to discover files.
For example, from the project root with the linked `ok` folder:

```python
from pathlib import Path
import runpy

catalog = runpy.run_path(str(Path('ok').resolve() / 'core' / 'skills.py'))
for skill in catalog['list_skills']():
    print(skill['id'], skill['path'])
```

Keep library instructions in their original location rather than copying them
into this project. Verify local API examples against the selected library; local
task/character references supplement its skills. If neither source has the
skills, report the missing library resources and use its setup guidance when
available; do not invent MCP tools or claim runtime validation.

## Use the library MCP workflow

Use ok-script MCP for inspecting and exercising game behavior. Discover native
ok-script tools when available; otherwise use the official MCP SDK from the
project environment with a local client script, as described by the library.
Read the selected server's `list_skills()` and relevant `get_skill(skill_id)`
results as well, and check that its project and library match the intended target.

On Windows, run Python MCP clients and test commands with `-X utf8` (or an
equivalent UTF-8 stream configuration). Task names and logs can contain Chinese
and emoji; a console encoding failure is not a server/task failure.

Reuse a live server for this project. Discover it through the configured artifact
directory, normally `logs/mcp/connections/*.json`, with `connection.json` as a
compatibility fallback. Prefer the library's `discover_mcp_servers()` helper when
available; validate process identity and its listener, use its actual URL and
bearer header, and keep tokens out of output. If no server is running, follow the
library's development skill and the project's launcher/config to start it. On
Windows, launch background helpers hidden. Do not assume a fixed port or replace
an active user GUI merely to start development; follow the library's ownership
rules.

For existing tasks, call `list_tasks()`, edit the returned source in place, and
call `reload_tasks(task_ids=[...])` with discovered IDs. Wait for a successful
terminal `get_run_status()` result before testing. A failed reload leaves old
instances in place. New registrations and changed non-plugin helpers, including
`src/char` modules and combat helpers, require restarting the owned runtime;
reloading a task alone does not refresh those imported dependencies.
Group related helper, registration, and asset edits and run their offline checks
before restarting to test a coherent revision. Do not save restart time by
exercising stale imported code or changing the rotation inside the harness.

Exercise the registered implementation through a thin `run_task` harness with an
absolute file path. Follow the library's `Task(BaseTask)` contract with
`reset_to_start()`, `verify_start_state()`, and `run()`. Reuse project recovery and
registered tasks, assert visible game results, and keep behavior in production
modules. Wait until `succeeded`, `failed`, or `cancelled` before submitting again;
`stopping` still owns the executor. Inspect returned local logs and screenshots,
including screenshot freshness. Follow the library's GUI lifecycle checks when
the change affects the user task card or normal scheduler.

For Windows input failures, follow the selected library development skill's
Windows input reference when available. Check runtime/target privileges before
changing backends, and verify buttons, keys, and drags separately through MCP.
Keep tool discovery/output narrow: filter tool metadata by relevant names, read
bounded log tails, and capture at state changes or failures rather than repeatedly
printing complete catalogs or unchanged frames.

If the target game or MCP prerequisites cannot be made available within the
authorized work, continue useful code and offline checks and state the specific
runtime validation gap. Do not present an import, reload, or mocked click as
proof that the game behavior succeeded.

## Wuthering Waves input observations

In the tested Tacet Elimination event, a non-elevated runtime logged PostMessage
access-denied errors. After restarting the owned runtime with matching elevated
rights, ordinary menu/Start/result buttons worked through PostMessage. The tested
background board drag still had no visible effect; a foreground
`PynputInteraction` drag did exchange pieces and change accepted-move counters.
This is evidence for that event/action/backend, not a requirement to run every
Wuthering Waves action in the foreground or proof that background dragging is
impossible. Keep any fallback local to the affected gesture and verify focus
before using the real cursor.

For temporary event tasks, verify OCR against complete status-label regions,
distinguish completed from locked/time-gated stages, and handle first-time help
dialogs and board entrance/cascade animations before declaring recognition
failure. Validate visible reward settlement and a second run that skips completed
content. Respect a requested current-screen baseline rather than automatically
returning to the open world.

Use ok-script MCP for game development and real input/capture validation. Follow
the selected library's interface restrictions, including its prohibition on
Computer Use in this workflow. When GUI lifecycle is in scope, exercise the task
card only through permitted APIs and report any remaining GUI validation gap.

## Wuthering Waves Abyss validation

For an authorized restart, reuse the registered combat task's
`restart_combat_in_abyss()`. Character-info introductions and environment help
are optional: detect their presence before dismissing them, and continue when
they are absent. If recovery needs a new overlay handler, put it in the shared
production helper and cover both presence and absence rather than leaving the
fix only in a temporary test harness. Avoid blind Escape/close clicks that can
open another menu when no overlay exists.

Verify the actual party HUD and loaded character identities after reset. The
helper temporarily forces combat detection after starting; that flag alone is
not evidence that the arena or intended character is ready.

Choose completion assertions from the observed arena. Some simulation arenas
finish by exposing an exit objective instead of a separate success popup.
Confirm the relevant visible end state; loss of target or a truthy combat-task
return alone does not prove completion. Keep this distinct from validating an
individual character rotation or full-Concerto handoff.

## Apply project conventions

- For tasks, continue with [ok-script-tasks](../ok-script-tasks/SKILL.md) for local
  bases, metadata, registration, and bilingual behavior.
- For characters, continue with [ok-ww-characters](../ok-ww-characters/SKILL.md)
  for `BaseChar`, `CharFactory`, rotation timing, and feature labels.
- Use [ok-script-i18n](../ok-script-i18n/SKILL.md) when task UI strings change.
- Use the library's `write-test` skill and existing project fixtures for meaningful
  offline checks; verify actual capture and input effects through MCP.
