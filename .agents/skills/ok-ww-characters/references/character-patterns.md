# OK-WW Character Patterns

## Files To Inspect

- `src/char/BaseChar.py`: shared combat helpers, cooldown tracking, priority, forte and input helpers.
- `src/char/Healer.py`: healer priority behavior.
- `src/char/CharFactory.py`: imports, label-to-class registration, cooldowns, element ring index.
- `src/Labels.py`: enum of feature names generated from annotated assets. New character and mechanic features belong here after developer annotation.
- `src/task/BaseCombatTask.py`: `available`, `get_cd`, `has_cd`, `find_mouse_forte`, `find_e_forte`, `load_chars`, `switch_next_char`.
- `tests/TestChar.py`: screenshot-backed recognition and availability tests.

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

from src.char.BaseChar import BaseChar, Priority


class NewCharacter(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_special = -1

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
                start = time.time()
            elif self.is_forte_full():
                self.heavy_click_forte()
            elif self.click_resonance(send_click=False, time_out=1)[0]:
                pass
            else:
                self.click(interval=0.1)
            self.cycle_sleep()

    def do_get_switch_priority(self, current_char, has_intro=False, target_low_con=False):
        if has_intro:
            return Priority.FAST_SWITCH + 1
        return super().do_get_switch_priority(current_char, has_intro, target_low_con)
```

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

If `"new_character_special"` is not already in `Labels`, state that the developer must add and annotate it.

Long liberation or intro state:

```python
if self.click_liberation(wait_if_cd_ready=0):
    start = time.time()
    self.task.wait_until(lambda: self.task.in_team()[0], post_action=self.click, time_out=8)
    self.add_freeze_duration(start, time.time() - start)
```

Team synergy or intro priority:

```python
def do_get_switch_priority(self, current_char, has_intro=False, target_low_con=False):
    if has_intro and current_char.char_name in {"char_expected_outro"}:
        return Priority.MAX
    return super().do_get_switch_priority(current_char, has_intro, target_low_con)
```

## Registration Pattern

In `src/char/CharFactory.py`:

```python
from src.char.NewCharacter import NewCharacter

_char_dict_raw = {
    Labels.char_new_character: {
        "cls": NewCharacter,
        "res_cd": 10,
        "echo_cd": 25,
        "liberation_cd": 25,
        "ring_index": Elements.FIRE,
    },
}
```

Use existing `Elements`:

- `Elements.SPECTRO`
- `Elements.ELECTRIC`
- `Elements.FIRE`
- `Elements.ICE`
- `Elements.WIND`
- `Elements.HAVOC`

If multiple visual labels identify the same character, use a tuple:

```python
(Labels.char_new_character, Labels.char_new_character_alt): {"cls": NewCharacter, ...}
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

## Skill Page Extraction

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
- `res_cd`, `echo_cd`, `liberation_cd`, and `ring_index` match the page or current project convention.
- Existing tests pass. Add screenshot tests when new recognition labels or cooldown checks are introduced.
