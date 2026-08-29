import math

import win32api

from ok import TriggerTask, Logger

logger = Logger.get_logger(__name__)


class MouseResetTask(TriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config = {'_enabled': True}
        self.trigger_interval = 10
        self.name = "🖱️ Prevent Wuthering Waves from moving the mouse"
        self.description = "Turn on if you mouse jumps around"
        self.mouse_pos = None

    def enable(self):
        super().enable()
        self.run()

    def run(self):
        if not self.enabled or self.is_browser():
            return
        logger.debug('schedule mouse reset')
        self.post_mouse_reset(0.01)

    def post_mouse_reset(self, delay):
        if self.enabled:
            self.handler.post(self.mouse_reset, delay, remove_existing=True)

    def mouse_reset(self):
        if not self.enabled or self.is_browser():
            return
        try:
            current_position = win32api.GetCursorPos()
            if self.mouse_pos and self.hwnd and self.hwnd.exists and not self.hwnd.visible and self.executor.interaction and self.executor.interaction.capture:
                center_pos = self.executor.interaction.capture.get_abs_cords(self.width_of_screen(0.5),
                                                                             self.height_of_screen(0.5))
                close_to_center = math.sqrt(
                    (current_position[0] - center_pos[0]) ** 2
                    + (current_position[1] - center_pos[1]) ** 2
                ) < 50
                distance = math.sqrt(
                    (current_position[0] - self.mouse_pos[0]) ** 2
                    + (current_position[1] - self.mouse_pos[1]) ** 2
                )
                if distance > 200 and close_to_center:
                    logger.info(f'move mouse back {self.mouse_pos}')
                    win32api.SetCursorPos(self.mouse_pos)
                    self.mouse_pos = self.mouse_pos
                    self.post_mouse_reset(1)
                    return
            self.mouse_pos = current_position
            self.post_mouse_reset(0.002)
        except Exception as e:
            logger.error('mouse_reset exception', e)
