---
name: ok-script-tasks
description: Create and modify automation task classes for the ok-script Python library, including BaseTask one-time tasks, TriggerTask background tasks, task config UI metadata, registration in ok-script app config, custom ok_tasks scripts, and bilingual English/Chinese task behavior. Use when Codex needs to implement, refactor, review, or explain ok-script tasks in any project, independent of any particular app.
---

# OK Script Tasks

## Overview

Use this skill to create or modify tasks built on the PyPI `ok-script` library. Keep guidance generic to `ok-script`; inspect the current project only to discover its local base classes, scene helpers, feature names, and registration style.

When more detail is needed, read:

- `references/task-api.md` for task lifecycle, config, execution, GUI, and bilingual rules.
- `references/templates.md` for reusable one-time task, trigger task, feature/OCR, and registration templates.
- Use `$ok-script-i18n` after task creation when gettext catalogs need task strings added, synced, or compiled.

## Workflow

1. Inspect the target project for existing tasks, app config, and any project-specific base class.
   Prefer existing project helpers over inheriting directly from `BaseTask` when the project already has a base task class.
2. Decide the task type:
   - Use `BaseTask` or a project one-time base for user-started workflows that should finish and disable themselves.
   - Use `TriggerTask` for background checks that run repeatedly while enabled.
   - Mix in feature/OCR/project helpers only when the task actually needs them.
3. Add or update task metadata in `__init__`:
   `name`, `description`, `default_config`, `config_description`, `config_type`, `supported_languages`, icons, grouping, and scheduling flags.
4. Implement `run()` with small, observable steps.
   Use `self.log_info`, `self.log_warning`, `self.info_set`, `self.wait_until`, `self.next_frame`, `self.sleep`, `self.click_relative`, `self.find_one`, `self.wait_click_feature`, `self.ocr`, and `self.wait_ocr` instead of ad hoc polling or direct device calls.
5. Register the task according to the project style:
   built-in config list, `ok_tasks` custom task folder, or imported script package.
6. If the project uses gettext catalogs, sync task translations with `$ok-script-i18n`.
7. Validate with the project test or headless path when available.
   At minimum, import the task module and instantiate the class if device-dependent execution cannot be run.

## Bilingual Output

Support English and Chinese in both code review and generated code.

- Answer the user in the language they use. If unclear, use English with concise Chinese labels where useful.
- Prefer stable English config keys because config keys become persisted JSON fields. Add Chinese help in `config_description` or through the project's translation system.
- Include both English and Chinese OCR match text when the UI may appear in either language.
- Use `supported_languages` only to hide a task in unsupported locales. Common locale names are `en_US`, `zh_CN`, `zh_TW`, `ja_JP`, `ko_KR`, and `es_ES`.
- Do not hard-code assumptions from the source project used to study `ok-script` unless the target project explicitly uses them.

## Essential Rules

- Always call `super().__init__(*args, **kwargs)` before setting task fields.
- Do not bypass `Config`: set defaults in `self.default_config`; read values through `self.config.get(...)` after `after_init()` loads config.
- For `TriggerTask`, keep `self.default_config['_enabled']` intentional and set `trigger_interval` to avoid excessive polling.
- Return truthy from a trigger task only after it handled something meaningful; falsey return lets the executor continue scanning other trigger tasks.
- For one-time tasks, allow normal completion; the executor disables the task after `run()` returns.
- Keep direct sleeps short and use `wait_until`, `wait_ocr`, or `wait_click_feature` for state-dependent waiting.
- Avoid locale-specific config keys unless the project already follows that style.
