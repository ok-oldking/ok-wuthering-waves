from src.task.MouseResetTask import MouseResetTask


class WWOneTimeTask:

    def run(self):
        mouse_reset_task = self.executor.get_task_by_class(MouseResetTask)
        if mouse_reset_task.is_device_compatible():
            mouse_reset_task.run()
        activate = getattr(self.executor.interaction, 'activate', None)
        if callable(activate):
            activate()
        self.sleep(0.5)
