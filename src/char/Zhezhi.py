import time
import cv2
import numpy as np

from ok import color_range_to_bound
from src.char.BaseChar import BaseChar, Priority, text_white_color


class Zhezhi(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._resonance_blue = False
        self.char_carlotta = None
        self.forte = 0

    def reset_state(self):
        super().reset_state()
        self._resonance_blue = False
        self.char_carlotta = None
        self.forte = 0

    def do_perform(self):
        if self.char_carlotta is not None:
            return self.do_perform_interlock()
        if self.has_intro:
            self.continues_normal_attack(1.5)
        self.click_liberation()
        if (self._resonance_blue or self.resonance_blue()) and self.resonance_available():
            self._resonance_blue = False
            self.resonance_until_not_blue()
            return self.switch_next_char()
        elif self.resonance_available() and not self.is_forte_full():
            pass
        elif self.resonance_available() and self.is_forte_full():
            self.click_resonance()
            self.continues_normal_attack(0.8)
            self._resonance_blue = True
            return self.switch_next_char()
        if not self.click_echo():
            self.continues_normal_attack(0.1)
        self.switch_next_char()

    def resonance_until_not_blue(self):
        start = time.time()
        while not self.resonance_blue():
            if time.time() - start > 0.3:
                break
            self.check_combat()
            self.task.next_frame()
        while self.resonance_available() and self.resonance_blue():
            self.send_resonance_key()
            if self.need_fast_perform() and time.time() - start > 1.1:
                break
            if self.is_con_full() and (self.char_carlotta is None or self.con_lock()):
                break
            if time.time() - start > 4:
                break
            self.check_combat()
            self.task.next_frame()

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if self.char_carlotta is not None and self.char_carlotta.get_ready():
            return Priority.MAX - 1
        if self.char_carlotta is not None and self.forte == 0:
            return Priority.FAST_SWITCH
        if self.char_carlotta is not None and has_intro and self.forte < 3:
            return Priority.FAST_SWITCH
        return super().do_get_switch_priority(current_char, has_intro)

    def con_lock(self):
        return self.char_carlotta.get_ready() or self.get_current_con() < 0.6 or (
                    self.is_con_full() and not self.char_carlotta.get_ready())

    def do_perform_interlock(self):
        if self.has_intro:
            self.continues_normal_attack(1.3)
        if self.flying():
            self.task.wait_until(lambda: not self.flying(), post_action=self.click_with_interval, time_out=1.2)
            self.continues_right_click(0.05)
        if not self.resonance_blue() and self.judge_forte() < 3 and not (
                self.is_con_full() and self.char_carlotta.get_ready()):
            self.continues_normal_attack(1.4)
            if not self.char_carlotta.get_ready():
                return self.switch_next_char()
        if not self.resonance_blue() and self.resonance_available() and self.judge_forte() > 1 and not (
                self.is_con_full() and self.char_carlotta.get_ready()):
            if self.con_lock() and self.click_liberation():
                self.sleep(0.2)
            self.click_resonance()
            self.continues_normal_attack(0.8)
        if self.con_lock():
            if self.resonance_blue() and self.resonance_available():
                self.resonance_until_not_blue()
                if self.con_lock() and self.click_liberation(wait_if_cd_ready=0.5):
                    self.sleep(0.2)
                elif self.echo_available():
                    self.continues_right_click(0.05)
        self.click_echo(time_out=2)
        return self.switch_next_char()

    def judge_forte(self):
        box = self.task.box_of_screen_scaled(5120, 2880, 2164, 2675, 2900, 2685, name='zhezhi_forte', hcenter=True)
        self.task.draw_boxes(box.name, box)
        self.forte = self.calculate_forte_num(zhezhi_forte_color, box, 3, 12, 14, 100)
        return self.forte

    def resonance_blue(self):
        box = self.task.box_of_screen_scaled(5120, 2880, 2242, 2664, 2300, 2690, name='zhezhi_kagane', hcenter=True)
        self.task.draw_boxes(box.name, box)
        blue_percent = self.task.calculate_color_percentage(text_white_color, box)
        self.logger.debug(f'zhezhi_kagane percent: {blue_percent}')
        return blue_percent > 0.3

    def judge_frequncy_and_amplitude(self, gray, min_freq, max_freq, min_amp):
        height, width = gray.shape[:]
        if height == 0 or width < 64 or not np.array_equal(np.unique(gray), [0, 255]):
            return 0

        profile = np.sum(gray == 255, axis=0).astype(np.float32)
        profile -= np.mean(profile)
        n = np.abs(np.fft.fft(profile))
        amplitude = 0
        frequncy = 0
        i = 1
        while i < width:
            if n[i] > amplitude:
                amplitude = n[i]
                frequncy = i
            i += 1
        self.logger.info(f'forte with freq {frequncy} & amp {amplitude}')
        return (min_freq <= frequncy <= max_freq) or amplitude >= min_amp

    def calculate_forte_num(self, forte_color, box, num=1, min_freq=39, max_freq=41, min_amp=50):
        cropped = box.crop_frame(self.task.frame)
        lower_bound, upper_bound = color_range_to_bound(forte_color)
        image = cv2.inRange(cropped, lower_bound, upper_bound)

        forte = 0
        height, width = image.shape
        step = int(width / num)

        forte = num
        left = step * (forte - 1)
        while forte > 0:
            gray = image[:, left:left + step]
            score = self.judge_frequncy_and_amplitude(gray, min_freq, max_freq, min_amp)
            if score:
                break
            left -= step
            forte -= 1
        self.logger.info(f'Frequncy analysis with forte {forte}')
        return forte

    def resonance_available(self, current=None, check_ready=False, check_cd=False):
        if self.is_current_char and self.resonance_blue():
            return True
        return super().resonance_available()


zhezhi_forte_color = {
    'r': (185, 215),  # Red range
    'g': (240, 255),  # Green range
    'b': (235, 255)  # Blue range
}  # 198,255,249

zhezhi_blue_color = {
    'r': (160, 180),  # Red range
    'g': (240, 255),  # Green range
    'b': (245, 255)  # Blue range
}
