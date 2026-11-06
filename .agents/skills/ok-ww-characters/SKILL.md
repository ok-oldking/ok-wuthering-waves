---
name: ok-ww-characters
description: Create, modify, review, and test Wuthering Waves character automation under src/char using the ok-script library's development skills and MCP workflow. Use for character rotations, BaseChar logic, CharFactory registration, Labels features, and English/Chinese combat terminology.
---

# OK-WW Characters

## Overview

Use this skill for character combat logic in `src/char`. A character implementation translates game mechanics from a skill-description page or user notes into a `BaseChar` subclass, then registers the class in `src/char/CharFactory.py`.

Before developing or modifying character behavior, follow
[ok-script-develop](../ok-script-develop/SKILL.md). Read the library's own skills
from the linked `<cwd>/ok` folder first, falling back to the project's installed
`site-packages`, and use the library's MCP development workflow. The project
patterns here supplement those instructions. Character modules are imported
helpers rather than registered tasks: restart the owned runtime after changing
them before exercising the consuming combat task; task reload alone leaves
non-plugin character imports cached.

Read `references/character-patterns.md` for the detailed API, templates, and validation checklist.

## Workflow

1. Inspect nearby character classes before editing.
   Prefer recent characters with similar mechanics, for example aerial/stance characters, healer classes, liberation stance characters, or forte-heavy characters.
2. Read the provided character description page if one is given.
   Extract only automation-relevant mechanics: normal attack chain, resonance skill behavior, forte trigger, liberation state, echo timing, intro/outro interactions, cooldowns, and required UI indicators.
3. Map terminology consistently:
   - `echo` = 声骸 / 声骸技能
   - `resonance` = 共鸣技能
   - `forte` = 共鸣回路
   - `liberation` = 共鸣解放
   - `click` = 普通攻击
   - `heavy` = 重击
4. Create or update `src/char/<CharacterName>.py`.
   Implement a `BaseChar` or `Healer` subclass with `do_perform()` as the primary rotation.
5. Register the character in `src/char/CharFactory.py`.
   Add the import and `_char_dict_raw` entry with `Labels.<char_label>`, cooldowns, `liberation_cd` if non-default, and `ring_index`.
6. If the rotation needs new image/template detections, follow the library's
   `generate-templates` skill with real screenshots and the project's annotations
   and exporter. Preserve exact `Labels` names and verify the resulting detection.
   If source images are unavailable, report the required feature and evidence gap
   rather than fabricating labels or annotations.
7. Add or update tests only when screenshots exist or the change touches recognition/availability logic.
   Use existing `tests/TestChar.py` patterns.
8. Exercise the changed character through its consuming combat task using MCP,
   following the library's recovery, starting-state checks, and visible success
   assertions. Report any game state that could not be tested.

## Bilingual Rules

- Answer in the user's language. For mixed English/Chinese requests, include both key game terms when it helps.
- Keep Python method names and local variables in English unless the surrounding code already uses another style.
- Use Chinese comments only when they explain a game mechanic more clearly than English; keep comments sparse.
- Preserve exact `Labels` enum names used by assets and annotations.

## Character Description Pages

When a page such as `https://ww.nanoka.cc/character/1210/` is provided, use it as a mechanics reference, not as code truth. Convert the page's combat sections into automation decisions:

- Which action starts the damage loop?
- Which UI indicator proves a stance, forte, enhanced skill, or special attack is ready?
- Which action consumes the state?
- Should the character stay on field, switch after one action, or fast-switch on intro?
- Does liberation cause animation freeze or a long alternate state?

Always verify the implementation against this repo's helpers and available labels.

## Essential Rules

- Do not add a character class without registering it in `CharFactory.py`.
- Do not invent `Labels` feature names silently. Create and verify new features through the library's template workflow when evidence is available; otherwise document the required label and missing source image.
- Use `self.time_elapsed_accounting_for_freeze(...)` for rotation timing when liberation or intro animation can freeze time.
- Prefer `click_resonance`, `click_liberation`, `click_echo`, `heavy_attack`, `continues_normal_attack`, `heavy_click_forte`, `is_forte_full`, `has_long_action`, and `f_break` over raw key calls.
- Keep loops bounded by timeouts and call `self.task.next_frame()` or `self.sleep(...)` inside polling loops.
- Use `Priority` overrides only when switching behavior truly depends on intro, cooldown, healer timing, or a long buff window.
