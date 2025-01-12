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
        clicked_resonance, duration, _ = self.click_resonance(send_click=False)
        clicked_echo = self.click_echo()
        sleep_time -= self.time_elapsed_accounting_for_freeze(start)
        self.logger.debug('Sanhua to_sleep {}'.format(sleep_time))
        self.sleep(sleep_time)
        self.task.mouse_up()
        if clicked_resonance and not clicked_echo:
            after_sleep = 0.6
        else:
            after_sleep = 0.3
        if self.has_intro:
            after_sleep += 0.8
        self.sleep(after_sleep)
        self.switch_next_char()
