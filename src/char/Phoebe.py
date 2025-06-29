import time
import cv2
import numpy as np
import math
from enum import Enum

from src.char.BaseChar import BaseChar, Priority, forte_white_color
from src.char.Healer import Healer
from ok import color_range_to_bound


class State(Enum):
    SUCCESS = 1
    UNAVAILABLE = 2
    TIMEOUT = 3


class Phoebe(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.perform_intro = 0
        self.attribute = 0
        self.star_available = False
        self.char_zani = None
        self.attribute_mismatch = False
        self.state = {
            "enter_status": 0,
            "starflash_combo": 0,
            "liberation": 0,
            "outro": 0
        }

    def reset_state(self):
        super().reset_state()
        self.perform_intro = 0
        self.attribute = 0
        self.star_available = False
        self.char_zani = None

    def do_perform(self):
        self.last_outro_time = -1
        start = time.time()
        if self.attribute == 0:
            self.decide_teammate()
        if self.has_intro:
            self.continues_normal_attack(1.5)
        else:
            self.sleep(0.01)

        if self.attribute == 1:
            self.click_echo(time_out=0.2)
        if self.flying():
            self.logger.info('flying')
            self.continues_normal_attack(0.1)
            return self.switch_next_char()

        attribute_mismatch = self.check_attribute_mismatch()

        if self.attribute == 2 and self.char_zani is not None:
            if self.zani_linkage():
                return self.switch_next_char()

        wait_ui_time = 0.35 - (time.time() - start)
        if wait_ui_time > 0 and self.star_available and self.judge_forte() == 0:
            self.logger.info('wait for UI')
            self.continues_normal_attack(wait_ui_time)

        status_entered = self.absolution_or_confession()
        self.check_combat()
        if ((not attribute_mismatch or status_entered == State.SUCCESS) and
                self.star_available and
                self.click_liberation(send_click=True)
        ):
            self.state["liberation"] += 1
            self.check_combat()
        if status_entered == State.SUCCESS or self.judge_forte() > 0:
            self.starflash_combo()
        if self.resonance_available():
            if self.attribute == 2:
                self.click_resonance_once()
            else:
                self.click_resonance()
            return self.switch_next_char()
        self.continues_normal_attack(0.1)
        self.switch_next_char()

    def zani_linkage(self):
        self.logger.debug('zani linkage')
        result = self.get_zani_state()
        if self.char_zani.blazes >= 0.9:
            self.logger.info('stop applying spectro frazzle')
            if not self.resonance_available():
                if result == 0 or self.char_zani.liberation_time_left() > 3:
                    self.continues_normal_attack(1)
            else:
                self.click_resonance(send_click=False)
            return True
        if result == 1:
            self.cast_remaining_skills()
            return True

    def check_attribute_mismatch(self):
        self.logger.debug('check attribute mismatch')
        box = self.task.box_of_screen_scaled(3840, 2160, 1890, 2010, 1915, 2030, name='phoebe_middle_star',
                                             hcenter=True)
        self.task.draw_boxes(box.name, box)
        star_light_percent = self.task.calculate_color_percentage(phiebe_star_light_color, box)
        self.logger.debug(f'middle_star_light_percent {star_light_percent}')
        star_blue_percent = self.task.calculate_color_percentage(phiebe_star_blue_color, box)
        self.logger.debug(f'middle_star_blue_percent {star_blue_percent}')
        if star_light_percent > 0.25 or star_blue_percent > 0.25:
            if star_light_percent > star_blue_percent:
                attribute = 1
            else:
                attribute = 2
        else:
            self.star_available = False
            return False
        if self.attribute != attribute:
            self.logger.info('attribute mismatch')
            old_attribute = self.attribute
            self.attribute = attribute
            self.cast_remaining_skills(liber=False)
            self.attribute = old_attribute
            return True
        return False

    def cast_remaining_skills(self, liber=True):
        start = -1
        if self.attribute == 1:
            skill_count = 4
        elif self.attribute == 2:
            skill_count = 2
        else:
            return start
        self.logger.info('cast remaining skills')
        for _ in range(skill_count):
            if liber and self.state["liberation"] < 1:
                if self.liberation_available() and self.click_liberation(send_click=False):
                    self.state["liberation"] += 1
            if self.judge_forte() > 0:
                self.starflash_combo()
                start = time.time()
        return start

    def judge_forte(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 1633, 2004, 2160, 2014, name='phoebe_forte1', hcenter=True)
        if self.attribute == 1:
            forte = self.calculate_forte_num(phoebe_forte_light_color, box, 4, 9, 11, 25)
        else:
            forte = self.calculate_forte_num(phoebe_forte_blue_color, box, 2, 18, 20, 50)
        return forte

    def starflash_combo(self):
        self.logger.info('perform starflash_combo')
        start = time.time()
        check_forte = start
        condition = self.get_prayer_condition()
        if not condition() and not self.heavy_attack_ready():
            while not self.heavy_attack_ready():
                self.click()
                if time.time() - start > 5:
                    return
                if time.time() - check_forte > 1:
                    if condition() or self.judge_forte() == 0:
                        return
                else:
                    check_forte = time.time()
                self.check_combat()
                self.task.next_frame()
        if self.perform_heavy_attack():
            self.state["starflash_combo"] += 1

    def perform_heavy_attack(self):
        if self.absolution_or_confession() == State.UNAVAILABLE:
            self.logger.info('perform heavy_attack')
            flying = False
            outer_start = time.time()
            while self.heavy_attack_ready():
                if time.time() - outer_start > 2:
                    return False
                self.task.mouse_down()
                mouse_hold_start = time.time()
                while time.time() - mouse_hold_start < 0.5:
                    if not self.heavy_attack_ready():
                        self.task.mouse_up()
                        return True
                    if flying := self.flying():
                        break
                    self.task.next_frame()
                self.task.mouse_up()
                if flying:
                    self.logger.info('flying')
                    self.task.wait_until(lambda: not self.flying(),
                                         post_action=lambda: self.click(interval=0.1, after_sleep=0.1), time_out=2)
                    outer_start = time.time()
                self.check_combat()
                self.task.next_frame()
            return True
        return False

    def click_resonance_once(self):
        start = time.time()
        while self.resonance_available():
            self.check_combat()
            if time.time() - start > 0.5:
                return True
            self.send_resonance_key()
            self.task.next_frame()
        return False

    def confession_ready(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 3103, 1844, 3285, 2026, name='phoebe_resonance', hcenter=False)
        self.task.draw_boxes(box.name, box)
        blue_percent = self.calculate_color_percentage_in_masked(phoebe_blue_color, box, 0.425, 0.490)
        self.logger.debug(f'blue_percent {blue_percent}')
        return blue_percent > 0.15

    def heavy_attack_ready(self):
        return self.is_forte_full()

    def calculate_color_percentage_in_masked(self, target_color, box, mask_r1_ratio=0.0, mask_r2_ratio=0.0):
        cropped = box.crop_frame(self.task.frame)
        if cropped is None or cropped.size == 0:
            return 0.0
        h, w = cropped.shape[:2]

        r1 = int(math.floor(h * mask_r1_ratio))
        r2 = int(math.ceil(h * mask_r2_ratio))
        if r2 <= r1:
            return 0.0

        center = (w // 2, h // 2)
        ring_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(ring_mask, center, r2, 255, -1)
        if r1 > 0:
            cv2.circle(ring_mask, center, r1, 0, -1)

        lower_bound, upper_bound = color_range_to_bound(target_color)

        color_mask = cv2.inRange(cropped, lower_bound, upper_bound)

        combined_mask = cv2.bitwise_and(color_mask, ring_mask)

        match_count = cv2.countNonZero(combined_mask)
        total_mask_area = cv2.countNonZero(ring_mask)
        if total_mask_area == 0:
            return 0.0
        return match_count / total_mask_area

    def get_prayer_condition(self):
        if not self.check_middle_star():
            return self.is_forte_full
        elif self.confession_ready():
            return self.confession_ready
        else:
            return lambda: False

    def absolution_or_confession(self):
        self.task.wait_in_team_and_world(time_out=3, raise_if_not_found=False)
        condition = self.get_prayer_condition()
        if self.attribute == 2:
            key_down = lambda: self.task.send_key_down(self.get_resonance_key())
            key_up = lambda: self.task.send_key_up(self.get_resonance_key())
        else:
            key_down, key_up = self.task.mouse_down, self.task.mouse_up
        if condition():
            outer_start = time.time()
            while condition():
                if time.time() - outer_start > 2:
                    return State.TIMEOUT
                key_down()
                key_hold_start = time.time()
                while condition() or time.time() - key_hold_start < 0.5:
                    if time.time() - key_hold_start > 1:
                        break
                    self.task.next_frame()
                key_up()
                if self.flying():
                    self.logger.info('flying')
                    self.task.wait_until(lambda: not self.flying(),
                                         post_action=lambda: self.click(interval=0.1, after_sleep=0.1), time_out=2)
                    outer_start = time.time()
                self.task.next_frame()
            if self.attribute == 2:
                self.logger.info(f'Enters confession status')
            else:
                self.logger.info(f'Enters absolution status')
            self.continues_right_click(0.05)
            self.star_available = True
            self.reset_action()
            self.state["enter_status"] += 1
            return State.SUCCESS
        return State.UNAVAILABLE

    def switch_next_char(self, *args):
        if self.is_con_full():
            if self.attribute == 2:
                self.click_echo()
                self.state["outro"] += 1
        return super().switch_next_char(*args)

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if self.attribute == 0:
            self.decide_teammate()
        if self.attribute == 2:
            if self.get_zani_state() == 1 and not self.is_action_complete():
                return 10000
            if has_intro and self.get_zani_state() != 1 and isinstance(current_char, Healer):
                return 10000
        if not has_intro and self.last_outro_time > 0 and self.time_elapsed_accounting_for_freeze(self.last_outro_time,
                                                                                                  intro_motion_freeze=True) < 4.5:
            self.logger.info(f'performing outro, Priority {Priority.MIN}')
            return Priority.MIN
        else:
            return super().do_get_switch_priority(current_char, has_intro)

    def check_middle_star(self):
        if self.star_available:
            return True
        box = self.task.box_of_screen_scaled(3840, 2160, 1890, 2010, 1915, 2030, name='phoebe_middle_star',
                                             hcenter=True)
        if self.attribute == 1:
            forte_percent = self.task.calculate_color_percentage(phiebe_star_light_color, box)
            self.logger.debug(f'middle_star_light_percent {forte_percent}')
            if forte_percent > 0.25:
                self.star_available = True
                return True
        elif self.attribute == 2:
            forte_percent = self.task.calculate_color_percentage(phiebe_star_blue_color, box)
            self.logger.debug(f'middle_star_blue_percent {forte_percent}')
            if forte_percent > 0.25:
                self.star_available = True
                return True
        return False

    def decide_teammate(self):
        from src.char.Zani import Zani
        from src.char.Cartethyia import Cartethyia
        from src.char.HavocRover import HavocRover
        if char := self.task.has_char(Zani):
            self.char_zani = char
            self.attribute = 2
        elif self.task.has_char((Cartethyia, HavocRover)):
            self.attribute = 2
        else:
            self.attribute = 1
        self.logger.debug(f"set attribute: {'support' if self.attribute == 2 else 'attacker'}")

    def judge_frequncy_and_amplitude(self, gray, min_freq, max_freq, min_amp):
        height, width = gray.shape[:]
        if height == 0 or width < 64 or not np.array_equal(np.unique(gray), [0, 255]):
            return 0

        white_ratio = np.count_nonzero(gray == 255) / gray.size
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
        return (min_freq <= i <= max_freq) or amplitude >= min_amp

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
            self.logger.debug('Frequncy analysis error, return the forte before mistake.')
        self.logger.debug(f'Frequncy analysis with forte {forte}')
        return forte

    def get_zani_state(self):
        if self.attribute == 2 and self.char_zani is not None:
            return self.char_zani.get_state()

    def is_action_complete(self):
        if self.attribute != 2:
            return False
        self.logger.debug(
            f'state_liberation {self.state["liberation"]} state_starflash_combo {self.state["starflash_combo"]}')
        if self.state["liberation"] >= 1 and self.state["starflash_combo"] >= 2:
            return True
        return False

    def reset_action(self):
        if self.attribute == 2:
            self.logger.info(f'reset action')
            self.state = {
                "enter_status": 0,
                "starflash_combo": 0,
                "liberation": 0,
                "outro": 0
            }

    def is_forte_full(self):
        if not self.star_available:
            return super().is_forte_full()
        elif self.attribute == 1:
            box = self.task.box_of_screen_scaled(3840, 2160, 2283, 1993, 2302, 2017, name='forte_full', hcenter=True)
        else:
            box = self.task.box_of_screen_scaled(3840, 2160, 2253, 1993, 2272, 2017, name='forte_full', hcenter=True)
        self.task.draw_boxes(box.name, box)
        mean_val = contrast_val = 0
        if self.task.calculate_color_percentage(forte_white_color, box) > 0.08:
            cropped = box.crop_frame(self.task.frame)
            gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
            mean_val = np.mean(gray)
            contrast_val = np.std(gray)
            self.logger.debug(f'is_forte_full mean {mean_val} contrast {contrast_val}')
        return mean_val > 190 and contrast_val > 40


phoebe_blue_color = {
    'r': (124, 134),  # Red range
    'g': (176, 186),  # Green range
    'b': (250, 255)  # Blue range
}

phoebe_light_color = {
    'r': (250, 255),  # Red range
    'g': (250, 255),  # Green range
    'b': (175, 185)  # Blue range
}

phoebe_forte_light_color = {
    'r': (240, 255),  # Red range
    'g': (240, 255),  # Green range
    'b': (165, 195)  # Blue range
}

phoebe_forte_blue_color = {
    'r': (225, 255),  # Red range
    'g': (225, 255),  # Green range
    'b': (190, 225)  # Blue range
}

phiebe_star_light_color = {
    'r': (235, 255),  # Red range
    'g': (220, 250),  # Green range
    'b': (160, 190)  # Blue range
}

phiebe_star_blue_color = {
    'r': (240, 255),  # Red range
    'g': (240, 255),  # Green range
    'b': (240, 255)  # Blue range
}
