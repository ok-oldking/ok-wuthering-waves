from src.task.MouseResetTask import MouseResetTask


class WWOneTimeTask:

    def run(self):
        mouse_reset_task = self.executor.get_task_by_class(MouseResetTask)
        mouse_reset_task.run()
        self.executor.interaction.activate()
        self.sleep(0.5)