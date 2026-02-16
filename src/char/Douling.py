import time

from src.char.Healer import Healer


class Douling(Healer):

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1.2)
        time_out = 1
        start_time = time.time()
        while time.time() - start_time < time_out and not self.is_con_full():
            if self.click_liberation(wait_if_cd_ready=False):
                self.sleep(0.001)
                continue
            elif self.click_resonance(send_click=True, time_out=0):
                self.sleep(0.001)
                continue
            else:
                self.click()
                self.sleep(0.1)
        self.click_echo(time_out=0)
        self.switch_next_char()
