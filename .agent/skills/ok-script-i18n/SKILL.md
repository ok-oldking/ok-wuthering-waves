---
name: ok-script-i18n
description: Add, sync, repair, and compile gettext translations for ok-script Python task classes and task metadata. Use when Codex needs to translate or internationalize BaseTask and TriggerTask names, descriptions, default_config keys or values, config_description help text, config_type options, OCR-facing UI strings, or locale-specific ok.po catalogs in ok-script style projects.
---

# OK Script i18n

## Overview

Use this skill for gettext translation work in ok-script projects that keep catalogs under `i18n/<locale>/LC_MESSAGES/ok.po`. It complements `$ok-script-tasks`: create task behavior with the task skill, then use this skill to keep task UI strings translated and compiled.

## Workflow

1. Inspect the target task file and collect user-facing task metadata:
   - `self.name`
   - `self.description`
   - keys and string values in `self.default_config`
   - string values in `self.config_description`
   - dropdown, multi-selection, list, and button option strings in `self.config_type`
   - OCR text lists only when they are user-visible or intended to be localized
2. Discover locales by listing `i18n/*/LC_MESSAGES/ok.po`.
   Do not hard-code a fixed language list.
3. Check whether each source string already exists in every catalog.
4. Add missing `msgid` blocks to every locale.
   Preserve existing `msgstr` values unless the user asks to revise translations.
5. Translate missing entries into every locale present in the repo.
6. Compile every changed `ok.po` into `ok.mo`.
7. Verify catalog syntax and check for duplicate `msgid` entries.

## Helper Script

Use `scripts/task_i18n_helper.py` when helpful:

```powershell
.\.venv\Scripts\python.exe .agent\skills\ok-script-i18n\scripts\task_i18n_helper.py scan --task src\task\DailyTask.py
.\.venv\Scripts\python.exe .agent\skills\ok-script-i18n\scripts\task_i18n_helper.py check --i18n i18n
.\.venv\Scripts\python.exe .agent\skills\ok-script-i18n\scripts\task_i18n_helper.py compile --i18n i18n
```

The scanner is a helper, not a substitute for reading the task. It finds common literal strings but can miss values built through constants, imports, f-strings, comprehensions, or helper functions.

## Catalog Rules

- Keep `msgid` exactly equal to the source string used by the code.
- Append new entries near the end if the catalog is not otherwise sorted.
- Do not add log-only strings unless the user explicitly asks.
- Focus on GUI-visible task metadata, config labels, config options, and help text.
- Empty `msgstr` is acceptable only when that locale intentionally falls back to the source language.
- Preserve translator comments, flags, previous `msgid` data, and existing entry order when possible.
- After editing `.po`, always compile `.mo`.

## Translation Guidance

- Prefer concise UI text over literal word-for-word translation.
- Keep placeholders, punctuation required by code, and hotkey names unchanged.
- Keep config keys stable when they are persisted in JSON. Translate the catalog entry for display, not the Python key, unless the project already stores localized keys.
- For Chinese locales, distinguish Simplified (`zh_CN`) and Traditional (`zh_TW`) when both catalogs exist.
- For option lists, translate each option string that appears in the UI.

## Integration With Task Work

When adding or modifying an ok-script task:

1. First use `$ok-script-tasks` to implement the task and identify user-facing strings.
2. Then use `$ok-script-i18n` to sync gettext catalogs for those strings.
3. Compile catalogs and include changed `.po` and `.mo` files in the final change summary.
