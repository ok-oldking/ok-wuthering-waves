import time

from src.char.BaseChar import BaseChar


class YangYangSp(BaseChar):
    INTRO_PERFORM_DURATION = 8.0
    PERFORM_DURATION = 2.6

    def do_perform(self):
        duration = self.INTRO_PERFORM_DURATION if self.has_intro else self.PERFORM_DURATION
        start = time.time()
        self.task.mouse_down()
        try:
            while self.time_elapsed_accounting_for_freeze(start) < duration:
                if self.liberation_available():
                    if not self.click_liberation(send_click=False, wait_if_cd_ready=0):
                        self.task.next_frame()
                    else:
                        duration += 2
                elif self.resonance_available():
                    if not self.click_resonance(send_click=False, time_out=0.5)[0]:
                        self.task.next_frame()
                else:
                    self.task.next_frame()
        finally:
            self.task.mouse_up()
        self.switch_next_char()
