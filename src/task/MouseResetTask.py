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
        self.running_reset = False
        self.mouse_pos = None
        self.reset_loop_id = 0

    def enable(self):
        super().enable()
        self.start_reset()

    def disable(self):
        super().disable()
        self.stop_reset('disabled')

    def run(self):
        if self.is_browser():
            return
        if self.enabled and not self.running_reset:
            self.start_reset()

    def start_reset(self):
        if self.running_reset:
            return
        logger.info('start mouse reset')
        self.running_reset = True
        # bump the loop id so callbacks from a previous loop are ignored
        self.reset_loop_id += 1
        loop_id = self.reset_loop_id
        self.handler.post(lambda: self.mouse_reset(loop_id), 0.01)

    def stop_reset(self, reason):
        if self.running_reset:
            logger.info(f'mouse reset stopped: {reason}')
        self.mouse_pos = None
        self.running_reset = False
        # invalidate callbacks still queued from the stopped loop
        self.reset_loop_id += 1

    def mouse_reset(self, loop_id):
        if loop_id != self.reset_loop_id or not self.enabled:
            return
        if self.is_browser():
            self.handler.post(lambda: self.mouse_reset(loop_id), 1)
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
                    self.handler.post(lambda: self.mouse_reset(loop_id), 1)
                    return
            self.mouse_pos = current_position
            self.handler.post(lambda: self.mouse_reset(loop_id), 0.002)
        except Exception as e:
            logger.error('mouse_reset exception', e)
            self.handler.post(lambda: self.mouse_reset(loop_id), 1)
