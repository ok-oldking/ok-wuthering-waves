import time
import cv2
import numpy as np
from ok import color_range_to_bound
from src.char.BaseChar import BaseChar, Priority


class Ciaccona(BaseChar):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attribute = 0

    def skip_combat_check(self):
        return self.time_elapsed_accounting_for_freeze(self.last_liberation) < 2

    def reset_state(self):
        super().reset_state()
        self.attribute = 0

    def do_perform(self):
        if self.attribute == 0:
            self.decide_teammate()
        if self.has_intro:
            self.continues_normal_attack(0.8)
            forte = self.judge_forte()
            if forte < 3:
                self.continues_normal_attack(0.6)
                # a4抬手时获得量表，但后摇很长选择切人
                return self.switch_next_char()
        self.click_echo()
        if self.is_forte_full():
            # 夏空进场自动a1，这时长按重击会先放一个超长后摇的a2，不得已只能重击1.5秒了
            self.heavy_attack(1.5)
            return self.switch_next_char()
        self.click_resonance()
        if self.click_liberation():
            if self.attribute == 2:
                self.continues_click_a(0.6)
        self.switch_next_char()

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        # 队友菲比时开大唱满20秒。可能导致菲比满协奏时夏空和奶妈双锁切人
        # 其他队友时，夏空会在主c满协奏时打断大招切出
        if self.time_elapsed_accounting_for_freeze(self.last_liberation) < 20:
            if self.attribute == 2 or (self.attribute == 1 and not has_intro):
                return Priority.MIN
            else:
                return -100
        return super().do_get_switch_priority(current_char, has_intro)

    def continues_click_a(self, duration=0.6):
        start = time.time()
        while time.time() - start < duration:
            self.task.send_key(key='a')

    def judge_forte(self):
        if self.is_forte_full():
            return 3
        box = self.task.box_of_screen_scaled(3840, 2160, 1612, 1987, 2188, 2008, name='ciaccona_forte', hcenter=True)
        forte = self.calculate_forte_num(ciaccona_forte_color, box, 3, 12, 14, 37)
        if forte == 0:
            forte = self.calculate_forte_num(ciaccona_forte_color1, box, 3, 12, 14, 37)
        return forte

    def decide_teammate(self):
        for i, char in enumerate(self.task.chars):
            self.logger.debug(f'ciaccona teammate char: {char.char_name}')
            if char.char_name == 'char_phoebe':
                self.logger.debug('ciaccona set attribute: light dot')
                self.attribute = 2
                return
        self.logger.debug('ciaccona set attribute: wind dot')
        self.attribute = 1
        return

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
        self.logger.debug(f'forte with freq {frequncy} & amp {amplitude}')
        return (min_freq <= frequncy <= max_freq) or amplitude >= min_amp

    def calculate_forte_num(self, forte_color, box, num=1, min_freq=39, max_freq=41, min_amp=50):
        cropped = box.crop_frame(self.task.frame)
        lower_bound, upper_bound = color_range_to_bound(forte_color)
        image = cv2.inRange(cropped, lower_bound, upper_bound)

        forte = 0
        height, width = image.shape
        step = int(width / num)
        left = 0
        fail_count = 0
        warning = False
        while left + step < width:
            gray = image[:, left:left + step]
            score = self.judge_frequncy_and_amplitude(gray, min_freq, max_freq, min_amp)
            if fail_count == 0:
                if score:
                    forte += 1
                else:
                    fail_count += 1
            else:
                if score:
                    warning = True
                else:
                    fail_count += 1
            left += step
        if warning:
            self.logger.info('Frequncy analysis error, return the forte before mistake.')
        self.logger.info(f'Frequncy analysis with forte {forte}')
        return forte

    # 回路条不满时的颜色


ciaccona_forte_color = {
    'r': (70, 100),  # Red range
    'g': (240, 255),  # Green range
    'b': (180, 210)  # Blue range
}

# 回路条满时的颜色
ciaccona_forte_color1 = {
    'r': (120, 220),  # Red range
    'g': (240, 255),  # Green range
    'b': (240, 255)  # Blue range
}
