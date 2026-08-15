import time

from ok import Logger
from src.char.BaseChar import BaseChar


class YangYangSp(BaseChar):
    INTRO_PERFORM_DURATION = 8.0
    PERFORM_DURATION = 3.2
    LONG_PRESS_RELEASE_DELAY = 0.1
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
        self.task.mouse_down()
        resonance_available = 0
        echo_used = False
        try:
            while self.time_elapsed_accounting_for_freeze(start) < duration:
                if self.liberation_available():
                    self.logger.debug('liberation_available')
                    if not self.click_liberation(send_click=False, wait_if_cd_ready=0):
                        pass
                    else:
                        duration += 2
                elif self.resonance_available():
                    self.logger.debug('resonance_available')
                    if resonance_available == 0:
                        resonance_available = time.time()
                    if resonance_available != 0 and time.time() - resonance_available > 0.2:
                        self.logger.debug('resonance available for 0.2')
                        self.click_resonance(send_click=False, time_out=1)
                elif not echo_used:
                    resonance_available = 0
                    echo_used = self.click_echo(time_out=0)
                else:
                    resonance_available = 0
                self.sleep(0.05)
        finally:
            self.task.mouse_up()
            # Let the released heavy attack settle before another character reads
            # the shared long-action indicator.
            self.sleep(self.LONG_PRESS_RELEASE_DELAY, check_combat=False)
        self.switch_next_char()
