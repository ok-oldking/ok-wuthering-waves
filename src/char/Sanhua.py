import time

from src.char.BaseChar import BaseChar


class Sanhua(BaseChar):
    def do_perform(self):
        sleep_time = 0.8
        if self.has_intro:
            self.sleep(0.02)
        start = time.time()
        self.task.mouse_down()
        if self.has_intro:
            self.wait_intro(click=False, time_out=1.1)
        elif self.click_resonance(send_click=False):
            self.sleep(0.1, False)
        if self.click_liberation(send_click=False):
            sleep_time += 0.425
        sleep_time -= self.time_elapsed_accounting_for_freeze(start)
        self.logger.info('Sanhua to_sleep {}'.format(sleep_time))
        if sleep_time > 0:
            self.sleep(sleep_time, False)
        self.task.mouse_up()
        self.sleep(0.6)
        if self.has_intro:
            self.click_resonance(send_click=False)
            self.sleep(0.3)
        if self.get_current_con() == 1:
            self.sleep(0.1)
            self.click_echo()
            self.sleep(0.05)
        self.switch_next_char()
