import math

import win32api
from qfluentwidgets import FluentIcon

from ok.logging.Logger import get_logger
from ok.task.TriggerTask import TriggerTask

logger = get_logger(__name__)


class MouseResetTask(TriggerTask):

    def __init__(self):
        super().__init__()
        self.default_config = {'_enabled': True}
        self.trigger_interval = 10
        self.name = "Prevent Wuthering Waves from moving the mouse"
        self.description = "Turn on if you mouse jumps around"
        self.icon = FluentIcon.MOVE
        self.running = False
        self.mouse_pos = None

    def run(self):
        pass

    def on_create(self):
        super().on_create()
        self.trigger()

    def trigger(self):
        if self.enabled:
            if not self.running:
                logger.info('start mouse reset')
                self.running = True
                self.handler.post(self.mouse_reset, 0.01)
        else:
            self.running = False

    def mouse_reset(self):
        try:
            current_position = win32api.GetCursorPos()
            if self.mouse_pos and self.hwnd and self.hwnd.exists and not self.hwnd.visible:
                center_pos = self.hwnd.x + self.hwnd.width / 2, self.hwnd.y + self.hwnd.height / 2
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
                    self.mouse_pos = None
                    if self.enabled:
                        self.handler.post(self.mouse_reset, 1)
                    return
            self.mouse_pos = current_position
            if self.enabled:
                return self.handler.post(self.mouse_reset, 0.002)
        except Exception as e:
            logger.error('mouse_reset exception', e)
