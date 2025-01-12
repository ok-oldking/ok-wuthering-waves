import time

from src.char.BaseChar import BaseChar


class Sanhua(BaseChar):
    def do_perform(self):
        sleep_time = 0.65
        self.sleep(0.02)
        self.task.mouse_down()
        self.sleep(0.1)
        start = time.time()
        if self.has_intro:
            sleep_time -= 0.1
            self.wait_intro(click=False, time_out=1.1)
        if self.click_liberation(send_click=False):
            sleep_time += 0.40
            pass
        clicked, duration, _ = self.click_resonance(send_click=False)
        if not clicked:
            self.click_echo()
        sleep_time -= self.time_elapsed_accounting_for_freeze(start)
        self.logger.debug('Sanhua to_sleep {}'.format(sleep_time))
        self.sleep(sleep_time)
        self.task.mouse_up()
        self.sleep(0.45)
        self.switch_next_char()
