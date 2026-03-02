import time
import cv2
import numpy as np

from src.char.Healer import Healer, Priority
from ok import color_range_to_bound


class Verina(Healer):

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1.2)
        time_out = 1
        start_time = time.time()
        while self.time_elapsed_accounting_for_freeze(start_time) < time_out and not self.is_con_full():
            self.cycle_start()
            if self.click_liberation(wait_if_cd_ready=False):
                pass
            elif self.click_resonance(send_click=False, time_out=0)[0]:
                time_out += 0.2
            elif self.click_echo(time_out=0):
                pass
            elif self.is_mouse_forte_full():
                self.heavy_attack()
                break
            else:
                self.click()
            self.cycle_sleep()
        self.switch_next_char()
