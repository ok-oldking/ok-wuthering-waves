# Comparing noisy Abyss runs

Use this reference for diagnostic evaluation and improvement comparisons. Its
purpose is to distinguish repeatable automation behavior from game randomness
without discarding inconvenient runs.

## Conditions and random factors

Compare the same roster, builds/constellations, stage/enemy, game version,
effective roles, settings, opener, start resources, metric reader, and diagnostic
sampling rate. Reset character caches and the arena consistently. Record source
hashes and active overrides so an old class cannot masquerade as a new candidate.
Keep helper changes out of the measured intervention, or rerun both variants with
the same infrastructure. Record material latency/FPS/load changes and manual
interference rather than silently attributing them to code.

Use final team score for score stages and the last validated top-center timer
before success for time stages. Higher is better for both. Keep the raw metric;
wall time includes freezes/animations and is not a substitute. Elapsed game time
can be derived from the known stage timer minus remaining time for interpreting
clear speed, but preserve the requested remaining-time metric in the report.

Knockdowns, enemy movement/attacks, crit variance, targeting luck, and interrupted
combos can change the outcome. These also reveal robustness: a rotation that
gets hit more often may regress. Attach observations to frames/events when
possible. Do not infer crit counts from total score or invent an RNG correction.

## Trial design

Evaluation defaults to three runs and reports their spread as an initial sample,
not proof of an optimization. Scale the comparison to the question. A narrowly
reproduced recognition/decision regression can justify a correctness fix while
its speed effect remains unconfirmed. Do not impose a large default combat study
on every small character change. A single candidate clear can screen for obvious
problems; it cannot establish repeatable superiority. Larger balanced samples are
appropriate when a performance claim is actually needed and the budget permits.

Prefer matched A/B or balanced ABBA/BAAB ordering under comparable conditions,
with identical recovery and cache resets. Choose block order before seeing
outcomes. If switching built-in versions requires expensive restarts, use team
overrides where appropriate or grouped balanced blocks. Do not compare a new
candidate only against a convenient historical best run.

Before running, define a useful effect in score points, seconds remaining, or
reliability. Base it on the user's objective, measurement precision, and baseline
variability; do not choose a threshold after seeing a small gain. Allocate one
total run/time cap for the request, including diagnostics, controls, rejected
variants, replacements and confirmation. Revisions share the remaining budget;
they do not each receive a new allocation. Reserve fresh confirmation outside
candidate selection and report it even if it reverses the initial result. At
the cap, stop with an honest partial conclusion. A revised hypothesis alone is
not a reason to extend the same task indefinitely.

When recent controls also fail or conditions drift, keep those outcomes and
reassess comparability before spending more runs. A candidate failure alone does
not establish that the change caused it. Likewise, an unstable control is not
permission to excuse every candidate failure as RNG. Diagnose the visible event
and report what remains unknown.

## Failures, exclusions, and outliers

Preserve every attempt and classify its outcome before comparing averages:

- A clear with a knockdown, bad crit luck, or a slow enemy pattern is a normal
  gameplay outcome. Keep it in the main results.
- Death, game timeout, failed rotations, and unrecovered automation stalls count
  against completion/reliability. A technical label must not hide a candidate's
  recognition or input failures.
- External disconnection/manual interference, the wrong stage, broken capture,
  or genuinely unreadable metrics can make a comparison technically invalid.
  Retain them, explain the evidence, report their count, and apply the same
  score-independent exclusion/replacement rule to both variants.

Never replace missing OCR with zero or calculate apparent improvement only from
a candidate's successful runs while hiding failures. Report completion rate
alongside success-conditional score/time. Use an all-attempt penalty or composite
measure only if defined in advance. A clean-run subset can diagnose mechanics
but cannot replace the all-run conclusion.

Do not drop a poor result merely because it is far from the mean. A knockdown
screenshot explains a run; it does not make it invalid. If taking fewer knockdowns
is the intervention, that effect belongs in the main result.

## Convincing evidence

Show every attempt's outcome and relevant random-event notes, then summarize
count, mean, median, best/worst, range, and sample standard deviation or IQR.
For matched trials, report paired deltas with a consistent improvement direction.
Show completion rate and important failure/stagger measures separately.

Use uncertainty estimates suited to the design when sample size permits, such
as an interval over paired deltas or bootstrap over independent trial blocks.
State the method and limits: individual frames/attacks in one combat are not
independent additional trials. Small-sample or repeatedly peeked intervals are
not guarantees. Do not claim confidence for a best-of-many search without
accounting for selection and optional stopping.

An improvement is convincing when its typical effect is practically useful,
comparison supports a direction beyond sampling/measurement noise, fresh
confirmation is consistent, and reliability meets the accepted objective.
Prefer evidence that the intended mechanic improved as well. Make speed versus
reliability tradeoffs visible for the user's decision.

If a gain is within the observed spread, call it inconclusive and use the planned
next block only within the remaining allocation. Otherwise retain the best
supported version and report uncertainty. Select it using the requested objective,
mechanical evidence and completion/reliability before a best-of-one metric.
Distinguish a useful candidate from a confirmed performance improvement. One lucky
high score, a crit-heavy clip, or three wins without a comparable control is
insufficient. If the user stops testing, skip further confirmation/replacement
runs, preserve the evidence, and mark confirmation incomplete.
