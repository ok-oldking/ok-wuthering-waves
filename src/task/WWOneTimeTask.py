from ok import BrowserInteraction, PostMessageInteraction
from src.task.MouseResetTask import MouseResetTask

CLOSE_GAME_AFTER_TASK = 'Close Game After Task'


class WWOneTimeTask:

    def run(self):
        mouse_reset_task = self.executor.get_task_by_class(MouseResetTask)
        mouse_reset_task.run()
        if isinstance(self.executor.interaction, PostMessageInteraction):
            self.executor.interaction.activate()
        self.sleep(0.5)

    def add_close_game_after_config(self):
        self.default_config.update({CLOSE_GAME_AFTER_TASK: False})
        self.config_description.update(
            {CLOSE_GAME_AFTER_TASK: 'Close only the game after the task completes, keeping OK-WW running.'})

    def maybe_close_game_after_task(self):
        if not self.config.get(CLOSE_GAME_AFTER_TASK):
            return
        self.log_info('Close Game After Task enabled, closing the game and keeping OK-WW running')
        try:
            self.executor.device_manager.stop_hwnd()
        except Exception as e:
            self.log_error('Failed to close game after task', e)
