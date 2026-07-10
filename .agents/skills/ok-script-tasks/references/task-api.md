# ok-script Task API Reference

## Core Classes

Import commonly used task APIs from `ok`:

```python
from ok import BaseTask, TriggerTask, Logger, ConfigOption, run_task
```

`BaseTask` is the base for one-time tasks. Important fields initialized by the library include:

- `name`: Display name. Defaults to the class name.
- `description`: Short GUI description.
- `default_config`: Dict used to create and verify persisted config.
- `config_description`: Help text by config key.
- `config_type`: Explicit GUI widget metadata.
- `supported_languages`: Empty means all locales.
- `trigger_interval`: Minimum seconds between trigger runs.
- `icon`, `group_name`, `group_icon`: GUI presentation fields.
- `support_schedule_task`: Whether the task can be used by the schedule UI.

`TriggerTask` extends `BaseTask` for background tasks. It adds `_enabled` to `default_config`, loads enabled state from config in `on_create()`, and persists changes in `enable()` and `disable()`.

## Lifecycle

Tasks are instantiated with `executor` and `app`, then initialized by `after_init(executor=..., scene=...)`.

Use these hooks:

- `__init__`: Set metadata, default config, descriptions, widget types, intervals, icons, and language support.
- `on_create`: Run after config is loaded. Use sparingly; `TriggerTask.on_create()` already loads `_enabled`.
- `post_init`: Link to other tasks or expensive helpers after all built-in tasks are created.
- `run`: Main task behavior.
- `sleep_check`: Optional periodic callback during `self.sleep()` when `sleep_check_interval >= 0`.
- `on_destroy`: Cleanup resources.
- `validate_config`: Return a message string for invalid config, otherwise `None`.

## Executor Semantics

The executor checks one-time tasks first. A one-time task runs when enabled, then the executor disables it after `run()` returns.

Trigger tasks are scanned repeatedly. A trigger task runs only when `enabled` and `should_trigger()` returns true. `should_trigger()` uses `trigger_interval`:

- `trigger_interval = 0`: eligible on every scan.
- `trigger_interval = 5`: eligible at most once every 5 seconds.

If a trigger task `run()` returns truthy, the executor restarts trigger scanning from the beginning. Return truthy only when the task performed an action that should give higher-priority triggers another chance.

## Config Model

Use `self.default_config` for all task settings. `Config` persists only keys present in defaults and enforces default value types.

```python
self.default_config.update({
    "_enabled": True,
    "Retry Count": 3,
    "Target Text": "Start",
    "Accepted Text": ["Start", "开始"],
})
self.config_description.update({
    "Retry Count": "Maximum attempts before the task stops.",
    "Target Text": "Text to search before clicking.",
})
```

GUI widgets are inferred from default value type:

- `bool`: switch
- `int`: spin box
- `float`: double spin box
- `str`: line edit or text edit for long/multiline text
- `list`: editable list

Use `config_type` for explicit widgets:

```python
self.config_type = {
    "Mode": {"type": "drop_down", "options": ["Fast", "Safe"]},
    "Labels": {"type": "multi_selection", "options": ["A", "B", "C"]},
    "Notes": {"type": "text_edit"},
}
```

Supported explicit types seen in ok-script GUI code:

- `drop_down`
- `multi_selection`
- `global`
- `text_edit`
- `button`

## Task Registration

Built-in tasks are usually registered in the app config:

```python
config = {
    "onetime_tasks": [
        ["my_project.tasks.daily", "DailyTask"],
    ],
    "trigger_tasks": [
        ["my_project.tasks.auto_pick", "AutoPickTask"],
    ],
    "scene": ["my_project.scene", "MyScene"],
}
```

For custom task scripts, enable custom tasks if the app supports it:

```python
config["custom_tasks"] = True
```

Then place a `.py` file in `ok_tasks/`. The loader parses top-level classes and instantiates the first subclass of `BaseTask` or `TriggerTask`.

Headless helpers can run by index, name, class, or instance:

```python
from ok import run_task
from my_project.config import config
from my_project.tasks.daily import DailyTask

run_task(config, task=DailyTask, debug=True)
```

## Device, Feature, and OCR Helpers

Prefer task methods over direct executor/device access:

- Frames and waiting: `self.next_frame()`, `self.wait_until(...)`, `self.sleep(...)`
- Input: `self.click(...)`, `self.click_relative(...)`, `self.click_box(...)`, `self.send_key(...)`, `self.send_key_down(...)`, `self.send_key_up(...)`
- Feature detection: `self.find_one(...)`, `self.find_feature(...)`, `self.wait_click_feature(...)`, `self.get_box_by_name(...)`
- OCR: `self.ocr(...)`, `self.wait_ocr(...)`, `self.wait_click_ocr(...)`
- Status and logs: `self.log_info(...)`, `self.log_warning(...)`, `self.log_error(...)`, `self.info_set(...)`, `self.info_incr(...)`
- Coordination: `self.get_task_by_class(...)`, `self.run_task_by_class(...)`

## English and Chinese

Prefer bilingual matching at the data boundary:

```python
self.default_config.update({
    "Confirm Text": ["Confirm", "确定"],
    "Cancel Text": ["Cancel", "取消"],
})
```

Use stable config keys and bilingual descriptions:

```python
self.config_description.update({
    "Confirm Text": "Texts to accept as confirmation buttons. 确认按钮文本列表。",
})
```

If a task should be visible only in certain locales:

```python
self.supported_languages = ["en_US", "zh_CN"]
```

Use `self.tr("...")` for runtime messages only when the target project has translations for that string. Otherwise use concise bilingual text or keep logs in the user's requested language.

For gettext catalog work, use `$ok-script-i18n` to add or sync entries under `i18n/<locale>/LC_MESSAGES/ok.po` and compile changed catalogs to `ok.mo`.
