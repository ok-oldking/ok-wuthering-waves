from ok.ui.qt.kit.dialogs import Dialog

from src.gui.MultiAccountConfigTab import MultiAccountConfigTab


class MultiAccountConfigDialog(Dialog):
    """Edit the local account plan from the normal multi-account task settings."""

    def __init__(self, parent, task):
        super().__init__(parent, task.tr('Multi-account configuration'),
                         ok_text=task.tr('Save and Close'), cancel_text=task.tr('Close'))
        self.task = task
        self.editor = MultiAccountConfigTab(execution_owner=task)
        self.editor.executor = task.executor
        # Start/stop belongs to the task page, including scheduling and cancellation.
        self.editor.start_button.hide()
        self.editor.stop_button.hide()
        self.body.addWidget(self.editor)

    def _fit(self):
        window = self.parentWidget()
        self.panel.setFixedWidth(min(1040, max(320, window.width() - 48)))
        self.editor.setFixedHeight(min(620, max(160, window.height() - 200)))
        self.panel.layout().invalidate()
        self.panel.layout().activate()
        super()._fit()

    def validate(self):
        # Only a task that is *actually running* owns the plan.  An enabled
        # task may merely be queued or re-enabled by a schedule after a
        # restart; treating that as "running" silently skipped save_accounts
        # and made the user's saved configuration appear to disappear.
        if getattr(self.task, 'running', False):
            return True
        return self.editor.save_accounts(notify=False)
