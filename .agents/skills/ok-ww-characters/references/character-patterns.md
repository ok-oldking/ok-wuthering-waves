# OK-WW Character Patterns

## Files To Inspect

- `src/char/BaseChar.py`: shared combat helpers, cooldown tracking, priority, forte and input helpers.
- `src/char/CharFactory.py`: imports, label-to-class registration, cooldowns, element ring index.
- `src/char/Lily.py`: multi-stage heavy channel, persistent Liberation, and Concerto top-up before Outro.
- `src/Labels.py`: enum of feature names generated from annotated assets. New character and mechanic features belong here after developer annotation.
- `src/task/BaseCombatTask.py`: `available`, `get_cd`, `has_cd`, `find_mouse_forte`, `find_e_forte`, `load_chars`, `switch_next_char`.
- `tests/TestChar.py`: screenshot-backed recognition and availability tests.
- `tests/TestLily.py`: ready/channel/state negatives, portrait registration, and mouse-release regressions.

Use current source as the API authority. Healer behavior is configured through
`CharType.HEALER`; the current tree has no separate `Healer.py` base.

## Terminology

Use these names in code discussions and comments:

- `echo`: 声骸 / 声骸技能, usually `click_echo()` or `send_echo_key()`.
- `resonance`: 共鸣技能, usually `click_resonance()` or `send_resonance_key()`.
- `forte`: 共鸣回路, usually `is_forte_full()`, `is_mouse_forte_full()`, `is_e_forte_full()`, or character-specific feature checks.
- `liberation`: 共鸣解放, usually `click_liberation()` or `send_liberation_key()`.
- `click`: 普通攻击, usually `click()` or `continues_normal_attack(...)`.
- `heavy`: 重击, usually `heavy_attack(...)`, mouse hold, or `heavy_click_forte(...)`.

## Class Template

```python
import time

from src.char.BaseChar import BaseChar


class NewCharacter(BaseChar):
    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(0.8)
        else:
            self.wait_down()

        self.perform_rotation()
        self.switch_next_char()

    def perform_rotation(self):
        start = time.time()
        while self.time_elapsed_accounting_for_freeze(start) < 2.5:
            self.cycle_start()
            self.click_echo(time_out=0)
            if self.click_liberation(wait_if_cd_ready=0):
                self.f_break()
            elif self.is_forte_full():
                self.heavy_click_forte()
            elif self.click_resonance(send_click=False, time_out=1)[0]:
                pass
            else:
                self.click(interval=0.1)
            self.cycle_sleep()
```

This example assumes Liberation returns to the usual controls. Derive ordering
from the actual kit, and keep the overall rotation deadline anchored; resetting
it on every cast can defeat the bound. Add custom state or priority only when
the mechanic requires it.

## Common Rotation Patterns

Simple sub-DPS:

```python
def do_perform(self):
    if self.has_intro:
        self.continues_normal_attack(1.0)
    self.click_echo(time_out=0)
    self.click_liberation()
    self.click_resonance()
    self.continues_normal_attack(0.5)
    self.switch_next_char()
```

Forte-heavy character:

```python
if self.is_mouse_forte_full():
    self.heavy_click_forte(self.is_mouse_forte_full)
elif self.is_e_forte_full():
    self.send_resonance_key()
else:
    self.click()
```

Feature-gated special attack:

```python
def special_available(self):
    return bool(self.task.find_one("new_character_special", threshold=0.7))
```

Author and verify the named feature through the library's template workflow
before using it. If screenshots are unavailable, report the missing feature and
evidence gap instead of inventing an annotation.

Liberation animation handling and freeze accounting already live in
`click_liberation()`. Do not count the same animation twice. A persistent state
after the animation needs its own visible-state handling; see below.

Team synergy or intro priority:

```python
from src.char.BaseChar import SwitchPriority


def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
    if has_intro and current_char and current_char.char_name in {"char_expected_outro"}:
        return SwitchPriority.MUST
    return super().get_switch_priority(current_char, has_intro, target_low_con)
```

## Registration Pattern

In `src/char/CharFactory.py`:

```python
from src.char.BaseChar import CharType, Elements
from src.char.NewCharacter import NewCharacter

_char_dict_raw = {
    Labels.char_new_character: {
        "cls": NewCharacter,
        "char_type": CharType.SUB_DPS,
        "ring_index": Elements.FIRE,
    },
}
```

The current factory consumes role, element, and buff metadata; cooldown tracking
uses the live HUD. Do not add unused cooldown fields. Set `buff_time` when the
known team buff differs from the role default. Map the element by name: a data
site's numeric element IDs need not match `Elements` values.

Use existing `Elements`:

- `Elements.SPECTRO`
- `Elements.ELECTRIC`
- `Elements.FIRE`
- `Elements.ICE`
- `Elements.WIND`
- `Elements.HAVOC`

If multiple visual labels identify the same character, use a tuple:

```python
_char_dict_raw[(Labels.char_new_character, Labels.char_new_character_alt)] = {
    "cls": NewCharacter,
    "char_type": CharType.MAIN_DPS,
    "ring_index": Elements.FIRE,
}
```

## Labels and Features

Character portrait labels and combat mechanic labels must exist in `Labels` and template data before detection can work. Good names follow existing conventions:

- `char_<name>` for portrait recognition.
- `<name>_heavy`, `<name>_jump`, `<name>_lib_forte`, `<name>_e1`, `<name>_e2`, `<name>_human`, etc. for mechanic indicators.

When adding code that depends on a missing feature, include a clear note:

```text
Needs developer-added feature label: Labels.<name>_<mechanic>, used to detect <state/action>.
```

Do not claim the character is fully testable until the label asset exists.

### Tight crops and state separation

Keep portrait patches inside the face/hair and inside the factory's portrait
search box. Keep skill crops inside the distinctive symbol, excluding the
surrounding scene, hotkey text, cooldown digits, and animated glow where possible.
Inspect crop previews before export.

Test both the intended state and its closest visual alternatives after changing
the crop. Normalized template matching may consider differently tinted copies
of the same symbol identical. Lily's ready and channeling flowers required the
additional generic full-gauge cue; raising the match threshold was insufficient
after cropping to the inner symbol. Other characters may need different cues.

Keep independent positives and useful negatives alongside the source captures.
Verify portrait registration against other occupied slots, not just a self-match.

### Scoped exports with legacy assets

The split exporter removes destination features absent from the supplied COCO.
Do not export a new-feature-only subset directly into the main template folder.
If unrelated legacy source images are missing, retain the canonical annotations,
export the relevant subset into a separate staging folder, and merge only those
generated names into the runtime folder. Remove superseded geometry filenames
for those same names so one feature does not retain multiple crop definitions.
Preserve unrelated assets and follow the library's `generate-templates` workflow.

## Multi-stage Actions and Outro Handoffs

For a charged/channelled action, distinguish ready, resource consumed, channel
active, and finisher/animation completion. A disappearing full-gauge prompt can
mean the action just started. Bound each wait, refresh frames, and release held
buttons/keys in `finally`. Hold only through the intended action so a long hold
does not start another attack after the finisher.

Before placing Liberation in a generic loop, check what its second press does
and which controls remain available afterward. Lily's Slumberland hid E/echo/
normal attacks and changed Liberation to End, so the finisher and energy buildup
had to precede it. If that state breaks lock-on during handoff, any character
combat-check exception should depend on a visible active-state cue and end when
the state or current character changes; do not disable combat checks globally.

For supports whose Outro carries the buff, observe full Concerto and an accepted
switch. Account for cooldown-gated Intro/passive energy and for Liberation being
unavailable or failing. A bounded E/normal top-up can bridge a shortfall, but its
budget must fit the finisher's buff window. Lily's tested three-second budget is
character-specific, not a default for other supports.

## Skill Page Extraction

If a Nanoka page has no readable text, inspect its raw HTML for
`script[data-sveltekit-fetched]` entries. Parse their JSON and the embedded
`body` JSON for the character-data URL actually referenced by that page. This
provided Lily's skill trees, cooldowns, Intro, and Forte descriptions without a
browser session. Do not hard-code the observed data version or assume another
page has the same payload shape; retain the user-facing page as the reference.

From a character page, extract:

- Element and role clues.
- Cooldowns for resonance, echo, and liberation.
- Whether normal attack, heavy attack, resonance, echo, or liberation starts the core loop.
- Forte condition and consumption action.
- Enhanced resonance/libration states and their UI indicators.
- Intro/outro timing or teammate dependencies.
- Whether a skill is considered Basic Attack DMG, Echo Skill DMG, Resonance Skill DMG, or Liberation DMG only if it affects automation decisions.

Ignore damage multipliers unless timing, state duration, or priority depends on them.

## Validation Checklist

- New class file imports only what it uses.
- `super().__init__(*args, **kwargs)` is called before custom state setup.
- `do_perform()` always eventually calls `switch_next_char()` or intentionally returns after switching.
- Every polling loop has a timeout and frame/sleep progression.
- New feature labels are documented and not silently invented.
- `CharFactory.py` imports and registers the class.
- `char_type`, `buff_time`, and `ring_index` match the kit and current factory.
- Existing tests pass. Add screenshot tests when new recognition labels or cooldown checks are introduced.

Select MCP scenarios from the mechanics rather than requiring a fixed run count:

| Scenario | Evidence to check |
| --- | --- |
| Opening without Intro | Factory recognizes the actual slot; resource buildup, special action, and handoff succeed. |
| Return with Intro | Intro actually occurred; enhanced actions and full-Concerto Outro work when Liberation is on cooldown. |
| Multi-stage/state action | Ready and active states separate; finisher completes; a second press does not cancel the intended state. |
| Team integration | The registered combat task progresses to the arena's visible completion condition. |

Switch cooldown can reject the first input. Reuse a bounded switch helper and
observe the new active slot before continuing. `load_chars()` resets Intro and
other per-turn bookkeeping; set a test's Intro flag only after establishing a
real full-Concerto switch, not to manufacture an unobserved game state.

In screenshot tests that exercise availability/cooldown helpers, populate
`task.chars` and mark the current character; cooldown lookup calls
`get_current_char()`. Use the repository's runner, for example
`.\.venv\Scripts\python.exe -X utf8 run_test.py tests.TestLily`, and run separate
`TaskTestCase` modules in separate processes to isolate their runtimes.

Distinguish source self-matches, independent screenshot recognition, mocked input
intent, and actual MCP input outcomes when reporting validation. Keep reusable
fixtures and annotations; remove session-only probe/restart scripts when cleanup
is requested, after no running attempt depends on them.
