# Evaluating animated combat indicators

Use this when a character's attack depends on a changing icon, stance, charge,
or resource display. Evaluation collects evidence; character behavior changes
belong to an authorized improvement task.

## Separate observation, decision, and outcome

Keep these claims distinct:

1. The current frame matched or missed a template.
2. The automation selected a particular hold, retry, exit, or switch.
3. The game accepted the action and consumed, retained, or replenished a resource.

A missed match is not automatically a failed attack. A long hold after an earlier
aerial confirmation may be a valid ground re-entry after depletion. Conversely,
a short hold selected from stale aerial history may happen on the ground. Tie a
suspected bug to the ordered HUD frames, inputs, and visible result before calling
the action wrong. Correct an earlier interpretation when later frames contradict it.

## Capture the transitions

Collect representative frames before entry, with multiple/last charges, through
consumption flashes, on recovery, after final depletion, and during legitimate
re-entry. Include resource-full ground states and interrupted entries when
relevant. Release the initiating input in a diagnostic probe when useful, but
remember that a queued attack or animation can continue after release.

Inspect the actual pixels rather than treating a scripted phase name as ground
truth. A late "settled" frame may contain replenished charges. Classify absent
resources separately from obscured or transforming indicators. Preserve timestamps
and frame identity; a capture count is not a measured frame rate.

Report consecutive missed samples and their observed span. A gap between the
surrounding captures only bounds the missing interval. Frame-level match counts
are not whole-combat accuracy, and multiple frames from one fight are not extra
independent combat trials.

## Check coverage before changing timing

An icon can have different expressions, sizes, positions, transparency, and
consumption animations. A template matching one expression may miss a different
charge even in an otherwise clear frame. Check representative resolutions and
independent captures, including negatives, before changing a threshold or adding
a blanket delay.

If pixels are fully obscured, lowering the threshold cannot reconstruct them.
Use bounded temporal evidence or another independently observed cue for that
interval. A generic mouse prompt can describe both ground and aerial readiness;
generic flying detection may not describe a character's special state.

Follow the library's generate-templates workflow for actual new visual features:
retain the original screenshot, annotate/export it, and validate the generated
feature on independent frames. Source-image self-matches are insufficient. A
second template detecting the same head is not a second charge: require distinct
positions and test partial/final depletion. Treat an incomplete template bank's
count as a conservative observation, not an exact resource total.

## Improvement decisions

Prefer a narrow recognition correction when evidence supports it. If temporal
state is needed, define what confirms entry, what action consumes the evidence,
what ends it, and when new entry is allowed. A generic readiness hint must not
indefinitely renew an old special-state observation. Do not carry an aerial latch
through an entire rotation after the final charge disappears.

An estimated spare-charge budget must decrease when the corresponding input is
issued, expire, and require new visual evidence before replenishment. A grace
period cannot by itself prove spare charges exist. Compare any added waiting with
its lost attack time, buff windows, and re-entry opportunities.

When tests are authorized, use ordered real-frame cases for transient misses,
last-charge consumption, new ground readiness, interruption, and reset between
calls. Replay by timestamp when a held action spans several captured frames;
do not force every frame to be processed after every hold. Mark simulated timing
or constructed endpoints explicitly. Offline cases prove decisions/recognition;
MCP combat results provide the separate input/completion evidence.
