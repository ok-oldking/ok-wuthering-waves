# ok-script Task Templates

## Minimal One-Time Task

Use for a user-started workflow that should run to completion.

```python
from ok import BaseTask, Logger

logger = Logger.get_logger(__name__)


class ClaimRewardTask(BaseTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Claim Reward"
        self.description = "Open the reward screen and claim available rewards."
        self.default_config = {
            "Retry Count": 3,
            "Confirm Text": ["Claim", "领取"],
        }
        self.config_description = {
            "Retry Count": "Maximum attempts before stopping. 最大尝试次数。",
            "Confirm Text": "Button OCR text to click. 要点击的按钮 OCR 文本。",
        }

    def run(self):
        for attempt in range(self.config.get("Retry Count", 3)):
            self.info_set("Attempt", attempt + 1)
            button = self.wait_ocr(match=self.config.get("Confirm Text"), time_out=3)
            if button:
                self.click_box(button, after_sleep=1)
                self.log_info("Task completed", notify=True)
                return
            self.next_frame()
        self.log_warning("No reward button found")
```

## Trigger Task

Use for a background task that checks for a condition while enabled.

```python
from ok import TriggerTask


class AutoClosePopupTask(TriggerTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Auto Close Popup"
        self.description = "Close known popups when they appear."
        self.trigger_interval = 1.0
        self.default_config.update({
            "_enabled": True,
            "Close Text": ["Close", "关闭"],
        })
        self.config_description.update({
            "Close Text": "OCR text for popup close buttons. 弹窗关闭按钮文本。",
        })

    def run(self):
        close_button = self.ocr(match=self.config.get("Close Text"))
        if not close_button:
            return False
        self.click_box(close_button, after_sleep=0.5)
        self.log_info("Closed popup")
        return True
```

If inheriting a project base class, place `TriggerTask` before or after the project base according to local examples. Preserve the existing method resolution style.

## Feature-Based Task

Use project feature names from the target app's template matching data.

```python
from ok import BaseTask


class ClickFeatureTask(BaseTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "Click Feature"
        self.description = "Wait for a feature and click it."
        self.default_config = {
            "Feature Name": "start_button",
            "Threshold": 0.8,
        }

    def run(self):
        feature = self.config.get("Feature Name")
        threshold = self.config.get("Threshold", 0.8)
        self.wait_click_feature(
            feature,
            threshold=threshold,
            time_out=10,
            raise_if_not_found=True,
            after_sleep=1,
        )
        self.log_info("Clicked feature")
```

## Config With Drop-Down and Multi-Selection

```python
self.default_config.update({
    "Mode": "Safe",
    "Enabled Labels": ["A"],
})
self.config_type.update({
    "Mode": {"type": "drop_down", "options": ["Safe", "Fast"]},
    "Enabled Labels": {"type": "multi_selection", "options": ["A", "B", "C"]},
})
self.config_description.update({
    "Mode": "Execution mode. 执行模式。",
    "Enabled Labels": "Labels allowed for matching. 允许匹配的标签。",
})
```

## Built-In Registration

```python
config = {
    "onetime_tasks": [
        ["my_app.tasks.claim_reward", "ClaimRewardTask"],
    ],
    "trigger_tasks": [
        ["my_app.tasks.auto_close_popup", "AutoClosePopupTask"],
    ],
}
```

## Custom ok_tasks Script

For an app with `custom_tasks` enabled, create one top-level task class in `ok_tasks/my_task.py`:

```python
from ok import BaseTask


class MyCustomTask(BaseTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "My Custom Task"
        self.default_config = {"Message": "Hello"}

    def run(self):
        self.log_info(self.config.get("Message"))
```

The loader scans top-level classes and instantiates the first subclass of `BaseTask` or `TriggerTask`.

## Validation Checklist

- Import succeeds with the target project's interpreter.
- Class can be instantiated by ok-script with `executor` and `app` keyword args.
- `super().__init__` runs before task metadata changes.
- Every user-editable setting appears in `default_config`.
- Every `config_type` key also exists in `default_config`.
- Trigger tasks include `_enabled` and a sensible `trigger_interval`.
- OCR text covers English and Chinese when the target UI may use both.
- Registration path and class name match the real module.
