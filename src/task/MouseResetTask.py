import math

import win32api
from qfluentwidgets import FluentIcon

from ok import TriggerTask, Logger

logger = Logger.get_logger(__name__)


class MouseResetTask(TriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config = {'_enabled': True}
        self.group_name = "Diagnosis"
        self.group_icon = FluentIcon.ROBOT
        self.trigger_interval = 10
        self.name = "Prevent Wuthering Waves from moving the mouse"
        self.description = "Turn on if you mouse jumps around"
        self.icon = FluentIcon.MOVE
        self.running_reset = False
        self.mouse_pos = None

    def run(self):
        if self.is_browser():
            return
        if self.enabled:
            if not self.running_reset:
                logger.info('start mouse reset')
                self.running_reset = True
                self.handler.post(self.mouse_reset, 0.01)
        else:
            self.running_reset = False

    def mouse_reset(self):
        if self.is_browser():
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
                    if self.enabled:
                        self.handler.post(self.mouse_reset, 1)
                    return
            self.mouse_pos = current_position
            if self.enabled:
                return self.handler.post(self.mouse_reset, 0.002)
        except Exception as e:
            logger.error('mouse_reset exception', e)
