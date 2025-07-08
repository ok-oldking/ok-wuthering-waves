import time
import cv2
import numpy as np

from src.char.Healer import Healer, Priority
from ok import color_range_to_bound


class Verina(Healer):
    def count_liberation_priority(self):
        return 2

    def do_perform(self):
        if self.has_intro:
            self.heavy_attack(1.5)
            return self.switch_next_char()
        self.wait_down()
        liberated = self.click_liberation()
        self.click_resonance(send_click=False)
        self.click_echo(time_out=0.1)
        if self.is_forte_full():
            self.heavy_attack()
        elif not liberated:
            self.click_liberation(wait_if_cd_ready=1)
        self.switch_next_char()
