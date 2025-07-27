import time

from src.char.BaseChar import BaseChar


class Sanhua(BaseChar):
    def do_perform(self):
        liber_clicked = False
        sleep_time = 0.8
        if self.has_intro:
            self.sleep(0.02)
        start = time.time()
        self.task.mouse_down()
        self.wait_down(click=False)
        if self.click_liberation(send_click=False):
            liber_clicked = True
            self.sleep(0.15, False)
        elif self.resonance_available():
            self.task.mouse_up()
            self.click_resonance(send_click=False)
            start = time.time()
            self.task.mouse_down()
            self.sleep(0.1, False)
        sleep_time -= self.time_elapsed_accounting_for_freeze(start)
        self.logger.info('Sanhua to_sleep {}'.format(sleep_time))
        if sleep_time > 0:
            self.sleep(sleep_time, False)
        self.task.mouse_up()
        self.sleep(0.6)
        if liber_clicked:
            self.click_resonance(send_click=False)
            self.sleep(0.3)
        if self.is_con_full():
            self.click_echo()
        self.switch_next_char()
