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
        while time.time() - start_time < time_out and not self.is_con_full():
            if self.click_liberation(wait_if_cd_ready=False):
                self.sleep(0.001)
                continue
            elif self.click_resonance(send_click=False, time_out=0):
                self.sleep(0.001)
                continue
            elif self.heavy_click_forte(self.is_mouse_forte_full):
                self.sleep(0.001)
                break
            else:
                self.click()
                self.sleep(0.1)
        self.click_echo(time_out=0)
        self.switch_next_char()
