import time

from ok import Logger
from src.char.BaseChar import BaseChar


class YangYangSp(BaseChar):
    INTRO_PERFORM_DURATION = 8.0
    PERFORM_DURATION = 2.6
    HOLD_RESTART_INTERVAL = 1.2
    HOLD_RESET_DELAY = 0.02
    DISPLAY_NAME = 'Yangyang: Xuanling'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = Logger.get_logger(self.DISPLAY_NAME)

    @property
    def display_name(self):
        return self.DISPLAY_NAME

    def __repr__(self):
        return self.DISPLAY_NAME

    def do_perform(self):
        duration = self.INTRO_PERFORM_DURATION if self.has_intro else self.PERFORM_DURATION
        start = time.time()
        hold_started = self.start_long_press()
        try:
            while self.time_elapsed_accounting_for_freeze(start) < duration:
                if self.liberation_available():
                    clicked, hold_started = self.use_action_and_restart_long_press(
                        lambda: self.click_liberation(send_click=False, wait_if_cd_ready=0))
                    if not clicked:
                        self.task.next_frame()
                    else:
                        duration += 2
                elif self.resonance_available():
                    result, hold_started = self.use_action_and_restart_long_press(
                        lambda: self.click_resonance(send_click=False, time_out=0.5))
                    if not result[0]:
                        self.task.next_frame()
                elif self.echo_available():
                    _, hold_started = self.use_action_and_restart_long_press(
                        lambda: self.click_echo(time_out=0))
                elif time.time() - hold_started >= self.HOLD_RESTART_INTERVAL:
                    hold_started = self.restart_long_press()
                else:
                    self.task.next_frame()
        finally:
            self.task.mouse_up()
        self.switch_next_char()

    def start_long_press(self):
        self.task.mouse_down()
        return time.time()

    def restart_long_press(self):
        self.task.mouse_up()
        self.sleep(self.HOLD_RESET_DELAY, check_combat=False)
        return self.start_long_press()

    def use_action_and_restart_long_press(self, action):
        self.task.mouse_up()
        result = action()
        self.sleep(self.HOLD_RESET_DELAY, check_combat=False)
        return result, self.start_long_press()
