---
name: evaluate-team
description: Evaluate the currently equipped Wuthering Waves team through ok-script MCP using repeated Abyss combats, explain its observed rotation, and recommend character automation improvements. Defaults to three runs and supports final-score and remaining-time modes.
---

# Evaluate the current team

Use [ok-script-develop](../ok-script-develop/SKILL.md) and the selected library's
development/MCP instructions to connect to the current project's live runtime.
Use [ok-ww-characters](../ok-ww-characters/SKILL.md) when inspecting or instrumenting
characters. This is an agent workflow, not a new GUI task card.

## Evaluation scope and cleanup

Evaluation observes the current implementation. Do not change character combat
behavior, rotations, roles, priorities, recognition logic, timings, builds, or
settings. Character-code edits are limited to temporary logging and screenshots.
Report proposed fixes and configuration mismatches; applying improvements is a
separate task requiring the user's instruction. Do not fix them and resume the
same evaluation as if its baseline had stayed unchanged.

Prefer the supplied script's temporary instance wrappers: they add diagnostics
without editing character files and are restored by `ExitStack` on success,
failure, and cancellation. If character-source logging/screenshots are necessary,
save the exact pre-evaluation file bytes and a record of the instrumentation
patch before editing, including any active custom-team override. In `finally`,
remove only instrumentation added by this evaluation and restore the loaded
runtime implementation as well as the source files. Preserve all pre-existing
user changes; the baseline is the file at evaluation entry, not Git HEAD. If the
user edits the same file during evaluation, remove the diagnostic patch while
preserving their new edits. Keep logs, screenshots, and the report as artifacts.
Verify and report cleanup before declaring the evaluation complete. A process
crash requires cleanup from the saved patch/baseline on the next connection.

Honor a later "stop testing" or cleanup-only instruction immediately: stop the
batch driver as well as any active MCP attempt, wait for terminal cleanup, and
report partial results. Do not use the evaluator to apply retained code: its
`reset_to_start()` starts a combat. Follow
[runtime and cleanup guidance](references/runtime-cleanup.md) for an application-only
refresh with no arena recovery or new tests.

## Establish the team and hypothesis

First submit a read-only MCP task that gets the registered `AutoCombatTask`, calls
`load_chars()`, and records all three slots' concrete classes, recognition
confidence, effective roles, active character config (including C6/DPS switches),
resolved source file paths, and current character. Compare the effective roles
with the user's described build. A factory default is not proof of the intended
role: a C6 Roccia built as main DPS must actually report `MainDps` at runtime.
Inspect custom team code and imported overrides, even when their class names
match the built-in classes. Do not infer the team from portraits or
previous evaluations. If the arena/result screen hides the team, use the existing
Abyss recovery helper to reach a visible arena, then load it before evaluating.

Read those three character modules, their factory entries and team-specific class
substitutions, and relevant `BaseChar`/switch-selection helpers. Explain the
expected rotation, intro/outro handoffs, forte use, damage windows and support
behavior as a hypothesis from code. Distinguish that hypothesis from observed
behavior and from game mechanics that have not been verified.

## Configure and run

Keep the current team, builds, stage and combat settings. Default to **3 combats**;
honor a requested count. Diagnostic captures and interrupted combats are separate
attempts, not replacement clears; keep them in the attempt record. Choose the metric from the user's request or observed
stage, not from the mere presence of a countdown:

- **score**: use the settled final score on the result screen, higher is better.
- **remaining_time**: use the last valid top-center countdown **before visible
  success**, higher is better. Sample throughout combat because success removes
  the timer. Preserve the source frame, sample age and sampling interval; reject
  a sampling gap over two seconds before timer disappearance when ranking
  remaining-time runs. Also report the age at the visible success banner: a
  result animation can delay that banner after the timer has already vanished.
  Wall time is not an equivalent metric because game time can freeze.

The score-based arena also has a countdown: collect it as a secondary diagnostic
and use it to exercise timer recognition. This does not validate clear-time
ranking in the other Abyss type. Never replace an unreadable score/time with zero.
Keep different stages, builds, effective roles, and primary metrics in separate
baselines; do not combine score-mode and time-mode results into one average.

Account for random factors such as knockdowns, crit variation, enemy movement,
and interrupted attacks. Keep ordinary unlucky gameplay outcomes in the main
results, record events when observable, and report completion/reliability as
well as score/time spread. Do not infer exact crit counts from total damage or
discard slow runs to improve the average. Three runs are an initial sample and
do not prove that a proposed code change improves the team. For detailed rules
read [comparison guidance](../improve-team/references/comparisons.md).

Use the reusable MCP file task [scripts/evaluate_team.py](scripts/evaluate_team.py).
Its defaults are three score-mode runs. To override, make a local copy under
`logs/`, change `RUNS`, `METRIC`, or bounded timeouts, and submit that absolute
path with `run_task(file_path=...)`. The task uses the registered combat instance
and calls `restart_combat_in_abyss()` before every run, including the first.
Its recovery hook starts the first combat; verification requires the actual
countdown, and subsequent runs repeat the same recovery. Run from inside the
current Abyss arena, pause menu, or result screen. Do not navigate to a different
stage or replace the team to manufacture a better benchmark.

Use the current team's score (`队伍得分` / team score) in preference to a cumulative
total that can include other teams. Inspect the first run's timer and result images against OCR before trusting a
batch. If the current UI differs, adjust the timer region or score label/value
geometry using real frames. Result recognition must distinguish an ended combat
from visible success/failure. A combat-detection exception alone proves neither.
Record deaths, detection failures, timeouts and missing metrics as invalid runs.
Invalid for metric ranking does not remove an attempt from completion/reliability
counts. Preserve the failure and its last timer as diagnostic evidence, not as a
clear score/time. When progress stops, capture a heartbeat with the current
character, rotation duration, last input, last successful action, visible countdown
and a fresh screenshot. Compare actual visible effects with input logs: sending keys is not proof
that attacks happened. A character standing idle while the timer continues, or
combat detection returning false before the timer disappears, is an incomplete
combat. Capture it before recovery; never hide it behind an ESC/rechallenge or
count an interrupted diagnostic as a completed benchmark. Investigate both the
character loop and shared target/combat detection before blaming the character.
Brief party-HUD loss during an intro is a transition to observe through a bounded
wait; it is not, by itself, proof that combat ended.
Do not silently run extra combats until three favorable results are obtained.
Stop on unsafe recovery, changed team, cancellation or an unrecognized result.
Keep partial evidence and report completed/attempted/requested counts.

The script temporarily wraps frame capture and the recognized character instances
to record timer samples, rotation durations, successful skill-helper returns,
intro entries and confirmed switch-outs. It restores every wrapper and combat
setting in `finally`. Successful helper returns show automation decisions, not
damage attribution. Add focused character logging/screenshots only when the
existing trace cannot explain a suspected problem, following the cleanup rules
above. Keep the baseline fixed across runs. Do not restart OK-WW for ordinary
evaluation, wrapper changes, or changes to the submitted evaluation file: MCP
compiles that file again on the next submission.

For character-source instrumentation or cleanup, follow
[runtime and cleanup guidance](references/runtime-cleanup.md): refresh the current
team through its existing loader between combats and preserve user overrides.
Task reload does not refresh cached built-in character/helper imports. Evaluation
does not authorize behavior changes to those modules.

For recognition-dependent attacks, read
[state recognition guidance](references/state-recognition.md). Observe entry,
animation, consumption, exit, and legitimate re-entry. Distinguish a missed image
match, the selected action, and its visible consequence; none alone proves the
next. For failed switches, inspect party health/downed portraits and shared combat
detection before attributing the failure to a character. Report proposed fixes
without applying them during evaluation.

Poll MCP to a terminal state and read the per-run `evaluation.json`,
`events.jsonl`, result OCR and screenshots in its artifact directory. MCP's
`succeeded` status alone does not establish a valid metric. Inspect screenshot
freshness and failures before any retry. Keep connection credentials private.

## Report

Give a per-run table with outcome, primary metric, secondary countdown and sample
age, wall duration, opener and any invalidity reason. For comparable valid runs,
report count, mean, median, best, worst and range (sample standard deviation when
useful); say when the sample is too small or openings differed. Include the game
language/resolution, stage evidence, combat settings and instrumentation interval
so another evaluation can reproduce it.

Explain how the three characters actually cycled: field/rotation time, successful
liberation/resonance/echo calls, intro/outro transfers, and stalls or missed
windows supported by the trace. Link representative frames/events. Rank concrete
improvements by likely impact and confidence, linking the character methods and
explaining what evidence would verify each idea. Separate measured findings,
code-derived suspicions and game-mechanics assumptions. Do not claim per-character
DPS from screen scores or suggest untested changes as proven score increases.

After the report and diagnostic cleanup, offer an editable follow-up prompt for
[improve-team](../improve-team/SKILL.md). Invite build/rotation corrections, HTTP
links, and example videos with timestamps. The follow-up starts with suggestions
and user input; it does not automatically authorize or apply character changes.
For the Codex artifact follow-up UI, use this form with the actual report path:

```text
- :codex-followup[Plan team improvements]{prompt="Use $improve-team with the evaluation at <absolute report path>. First suggest prioritized improvements and invite my build details, links, videos, or rotation corrections before modifying character code."}
```
