import time
import cv2
import numpy as np

from src.char.Healer import Healer, Priority
from ok import color_range_to_bound


class Verina(Healer):
    def count_liberation_priority(self):
        return 2

    def do_perform(self):
        self.wait_down(click=False)

        if self.has_intro:
            self.heavy_attack(duration=0.05)
            self.wait_down(click=False)
        else:
            self.continues_normal_attack(1.2)

        if self.resonance_available():
            self.click_resonance(send_click=False, post_sleep=0.375)
        if self.echo_available():
            self.click_echo()
        if self.liberation_available():
            self.click_liberation()
            return self.switch_next_char()

        if self.is_mouse_forte_full():
            count = 0
            while not self.flying():
                self.task.jump()
                count += 1
                if count >= 10:
                    return self.switch_next_char()
            self.continues_normal_attack(0.8)

        return self.switch_next_char()
