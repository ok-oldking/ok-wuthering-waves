import time
import cv2
import numpy as np
import math
from enum import Enum

from src.char.BaseChar import BaseChar, SwitchPriority, forte_white_color
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
        self.char_rover = None
        self.attribute_mismatch = False
        self.first_rotation_done = False
        self._zanfei_guang = False
        self._liber_insert = False
        self._force_switch_me = False
        self._zanfei_first_outro_done = False
        self.state = {
            "enter_status": 0,
            "starflash_combo": 0,
            "liberation": 0,
            "outro": 0,
            "priority_liberation_cast": 0,
        }

    def reset_state(self):
        super().reset_state()
        self.perform_intro = 0
        self.attribute = 0
        self.star_available = False
        self.char_zani = None
        self.char_rover = None
        self.first_rotation_done = False
        self._zanfei_guang = False
        self._liber_insert = False
        self._force_switch_me = False
        self._zanfei_first_outro_done = False

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if self._force_switch_me:
            return SwitchPriority.MUST
        for char in self.task.chars:
            if char is not None and char is not self and getattr(char, "_force_switch_me", False):
                return SwitchPriority.NO
        if (
            not has_intro
            and self.last_outro_time > 0
            and (self.time_elapsed_accounting_for_freeze(self.last_outro_time, intro_motion_freeze=True) < 4.5)
        ):
            self.logger.info("performing outro, switch priority no")
            return SwitchPriority.NO
        return super().get_switch_priority(current_char, has_intro, target_low_con)

    def _force_switch_to(self, target):
        if target is None:
            return super().switch_next_char()
        for char in self.task.chars:
            if char is not None:
                char._force_switch_me = char is target
        try:
            return super().switch_next_char()
        finally:
            for char in self.task.chars:
                if char is not None:
                    char._force_switch_me = False

    def do_perform(self):
        if self._zanfei_guang and self._liber_insert:
            return self._do_liber_insert()
        self.last_outro_time = -1
        start = time.time()
        if self.attribute == 0:
            self.decide_teammate()
        if self.has_intro:
            self.continues_normal_attack(1.5)
        else:
            # 非变奏切人后会自然接一段普攻，先等它结算协奏，再抢大招。
            self.sleep(0.01)
        self._try_liberation_now()
        if self.attribute == 1:
            self.click_echo(time_out=0)
        if self.flying():
            self.logger.info("flying")
            self.continues_normal_attack(0.1)
            return self.switch_next_char()
        attribute_mismatch = self.check_attribute_mismatch()
        if self.attribute == 2 and self.char_zani is not None:
            if not self.star_available:
                self.absolution_or_confession()
            if self.zani_linkage():
                return self.switch_next_char()
        wait_ui_time = 0.35 - (time.time() - start)
        if wait_ui_time > 0 and self.star_available and self.judge_forte() == 0:
            self.logger.info("wait for UI")
            self.continues_normal_attack(wait_ui_time)
        status_entered = self.absolution_or_confession()
        self.check_combat()
        if (
            (not attribute_mismatch or status_entered == State.SUCCESS)
            and self.star_available
            and self.click_liberation(send_click=True)
        ):
            self.state["liberation"] += 1
            self.state["priority_liberation_cast"] = 1
            self.check_combat()
        if status_entered == State.SUCCESS or self.judge_forte() > 0:
            self.starflash_combo()
            self._try_liberation_now()
            max_starflash = 1 if self._zanfei_guang else 2
            if self.attribute == 2 and self.state["starflash_combo"] < max_starflash and (self.get_zani_state() != 1):
                self.logger.info("phoebe: try second starflash_combo")
                self.starflash_combo()
        self._try_liberation_now()
        if self.resonance_available():
            if self.attribute == 2:
                if not self._zanfei_guang and (not self.confession_ready()) and self.first_rotation_done:
                    self.click_resonance_once()
            else:
                self.click_resonance()
            self._ensure_first_rotation_con()
            return self.switch_next_char(_zanfei_full_tail=self._zanfei_guang)
        self.continues_normal_attack(0.1)
        self._ensure_first_rotation_con()
        self.switch_next_char(_zanfei_full_tail=self._zanfei_guang)

    def _do_liber_insert(self):
        """赞妮大招插入：starflash + 长按定身E + 有大招则放，切回赞妮（禁止短按传送/闪避起飞）。"""
        self._liber_insert = False
        self.logger.info("phoebe: zani liber insert short axis")
        if self.attribute == 0:
            self.decide_teammate()
        self._ensure_grounded("insert enter")
        self.logger.info("phoebe: insert settle after switch")
        self.sleep(0.5)
        if self.has_intro:
            self.continues_normal_attack(0.8)
            self._ensure_grounded("insert after intro na")
        if not self.star_available:
            self.absolution_or_confession(dodge_cancel=False)
            self._ensure_grounded("insert after confession")
        if self._try_liberation_now():
            self.logger.info("phoebe: liber insert cast liberation")
            self._ensure_grounded("insert after liber")
        if self.judge_forte() > 0 or self.heavy_attack_ready():
            if self.heavy_attack_ready():
                self.logger.info("phoebe: liber insert direct heavy (no dodge cancel)")
                if self.perform_heavy_attack():
                    self.state["starflash_combo"] += 1
            else:
                self.starflash_combo()
            self._ensure_grounded("insert after heavy")
        if self._try_liberation_now():
            self.logger.info("phoebe: liber insert cast liberation after starflash")
            self._ensure_grounded("insert after liber2")
        self._insert_long_press_dingshen_e()
        self._ensure_grounded("insert before switch")
        from src.char.Zani import Zani

        zani = self.char_zani or self.task.has_char(Zani)
        return self._force_switch_to(zani)

    def _ensure_grounded(self, tag=""):
        """插入轴落地，避免重击/技能后滞空切人。"""
        self.wait_down()
        if self.flying():
            self.logger.info(f"phoebe: wait land {tag}")
            self.task.wait_until(
                lambda: not self.flying(), post_action=lambda: self.click(interval=0.1, after_sleep=0.05), time_out=2.0
            )
            self.wait_down()

    def _insert_long_press_dingshen_e(self):
        """大招插入定身：E 可用则长按；绝不用短按二段传送。"""
        if not self.resonance_available():
            self.logger.info("phoebe: insert dingshen skip, E not ready")
            return False
        if self.confession_ready() or self.star_available:
            self.logger.info("phoebe: insert long-press E dingshen")
            key = self.get_resonance_key()
            self.task.send_key_down(key)
            hold_start = time.time()
            while time.time() - hold_start < 0.55:
                self.task.next_frame()
            self.task.send_key_up(key)
            self.sleep(0.05)
            return True
        self.logger.info("phoebe: insert dingshen skip, not confession/star state")
        return False

    def _ensure_first_rotation_con(self):
        """切人前补协奏：赞菲光每轮最多10秒；非赞菲光完整轴最多5秒。"""
        if self._zanfei_guang:
            if not self.is_con_full():
                self.logger.info(f"phoebe: zanfei wait full con before switch first_rot={not self.first_rotation_done}")
                self.continues_normal_attack(10.0, until_con_full=True)
            self.first_rotation_done = True
            return
        if not self.first_rotation_done:
            self.first_rotation_done = True
        start_con = self.get_current_con()
        if start_con == 1 or self.get_zani_state() == 1:
            return
        self.continues_normal_attack(5.0, until_con_full=True)
        end_con = self.get_current_con()
        self.logger.info(f"phoebe: full con fallback start={start_con} end={end_con} full={end_con == 1}")

    def zani_linkage(self):
        self.logger.debug("zani linkage")
        result = self.get_zani_state()
        if self.char_zani.blazes >= 0.9:
            self.logger.info("stop applying spectro frazzle")
            if not self.resonance_available():
                if result == 0 or self.char_zani.liberation_time_left() > 3:
                    self.continues_normal_attack(1, interval=0.15)
            elif not self._zanfei_guang and self.first_rotation_done and (not self.confession_ready()):
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
        star_light_percent = self.task.calculate_color_percentage(phoebe_star_light_color, box)
        self.logger.debug(f'middle_star_light_percent {star_light_percent}')
        star_blue_percent = self.task.calculate_color_percentage(phoebe_star_blue_color, box)
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
                self.task.next_frame()
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
                if self.flying():
                    self.shorekeeper_auto_dodge()
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
            self.continues_right_click(0.05)
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
        box = self.task.box_of_screen_scaled(2560, 1440, 2110, 1236, 2217, 1343, name='phoebe_resonance', hcenter=False)
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

    def absolution_or_confession(self, dodge_cancel=True):
        self.task.wait_in_team_and_world(time_out=3, raise_if_not_found=False)
        condition = self.get_prayer_condition()
        if self.attribute == 2:
            key_down = lambda: self.task.send_key_down(self.get_resonance_key())
            key_up = lambda: self.task.send_key_up(self.get_resonance_key())
        else:
            key_down, key_up = (self.task.mouse_down, self.task.mouse_up)
        if condition():
            outer_start = time.time()
            while condition():
                if time.time() - outer_start > 2:
                    return State.TIMEOUT
                key_down()
                key_hold_start = time.time()
                while condition() or time.time() - key_hold_start < 0.4:
                    if time.time() - key_hold_start > 1:
                        break
                    self.task.next_frame()
                key_up()
                if self.flying():
                    self.logger.info("flying")
                    self.task.wait_until(
                        lambda: not self.flying(),
                        post_action=lambda: self.click(interval=0.1, after_sleep=0.1),
                        time_out=2,
                    )
                    outer_start = time.time()
                self.task.next_frame()
            if self.attribute == 2:
                self.logger.info("Enters confession status")
            else:
                self.logger.info("Enters absolution status")
            if dodge_cancel:
                self.continues_right_click(0.05)
            self.star_available = True
            self.reset_action()
            self.state["enter_status"] += 1
            return State.SUCCESS
        return State.UNAVAILABLE

    def _try_liberation_now(self):
        """每次需要攻击前额外检查，有大招就释放，返回True表示已释放"""
        if self.star_available and (not self.flying()) and self.liberation_available():
            if self.click_liberation(send_click=True):
                self.state["liberation"] += 1
                self.state["priority_liberation_cast"] = 1
                self.check_combat()
                return True
        return False

    def _try_cast_liberation_before_switch(self):
        if self.attribute != 2:
            self.logger.info("phoebe: pre-switch liber diag=v5-pre-switch-r2 stage=soft outcome=attribute")
            return False
        if self.state.get("priority_liberation_cast"):
            self.logger.info("phoebe: pre-switch liber diag=v5-pre-switch-r2 stage=soft outcome=duplicate")
            return False
        if not self.star_available:
            self.logger.info("phoebe: pre-switch liber diag=v5-pre-switch-r2 stage=soft outcome=star-unavailable")
            return False
        if self.flying():
            self.logger.info("phoebe: pre-switch liber diag=v5-pre-switch-r2 stage=soft outcome=airborne")
            return False
        if not self.liberation_available():
            self.logger.info("phoebe: pre-switch liber diag=v5-pre-switch-r2 stage=soft outcome=liberation-unavailable")
            return False
        if self.click_liberation(send_click=True):
            self.state["priority_liberation_cast"] = 1
            self.state["liberation"] += 1
            self.check_combat()
            self.logger.info("phoebe: pre-switch liber diag=v5-pre-switch-r2 stage=soft outcome=cast-success")
            return True
        self.logger.info("phoebe: pre-switch liber diag=v5-pre-switch-r2 stage=soft outcome=cast-failed")
        return False

    def _settle_zanfei_liberation_before_switch(self):
        start = time.time()
        attempts = 0
        result = "already-success" if self.state.get("priority_liberation_cast") else "availability-timeout"
        if result != "already-success" and (not self.star_available):
            result = "star-unavailable"
        while result not in ("already-success", "star-unavailable") and time.time() - start < 1.0:
            if self.flying():
                result = "airborne-timeout"
                self.click(interval=0.1)
                self.task.next_frame()
                continue
            result = "availability-timeout"
            if self.liberation_available():
                attempts += 1
                if self.click_liberation(send_click=True):
                    self.state["priority_liberation_cast"] = 1
                    self.state["liberation"] += 1
                    self.check_combat()
                    result = "cast-success"
                    break
                if attempts >= 2:
                    result = "cast-failed-limit"
                    break
            self.task.next_frame()
        elapsed = min(time.time() - start, 1.0)
        self.logger.info(
            f"phoebe: pre-switch liber diag=v5-pre-switch-r2 stage=settlement result={result} elapsed={elapsed:.2f}s attempts={attempts}"
        )
        return result in ("already-success", "cast-success")

    def switch_next_char(self, *args, **kwargs):
        full_tail = bool(kwargs.pop("_zanfei_full_tail", False))
        self._try_cast_liberation_before_switch()
        if self.attribute == 2 and self.is_con_full():
            if full_tail and self._zanfei_guang and (not self._liber_insert):
                self._settle_zanfei_liberation_before_switch()
            self.click_echo()
            self.state["outro"] += 1
            if self._zanfei_guang and (not self._liber_insert):
                return self._zanfei_switch_on_full_con()
        return super().switch_next_char(*args, **kwargs)

    def _zanfei_switch_on_full_con(self):
        from src.char.Zani import Zani

        self._zanfei_first_outro_done = True
        target = self.char_zani or self.task.has_char(Zani)
        self.logger.info("phoebe: zanfei full-con outro -> Zani")
        return self._force_switch_to(target)

    def check_middle_star(self):
        if self.star_available:
            return True
        box = self.task.box_of_screen_scaled(3840, 2160, 1890, 2010, 1915, 2030, name='phoebe_middle_star',
                                             hcenter=True)
        if self.attribute == 1:
            forte_percent = self.task.calculate_color_percentage(phoebe_star_light_color, box)
            self.logger.debug(f'middle_star_light_percent {forte_percent}')
            if forte_percent > 0.25:
                self.star_available = True
                return True
        elif self.attribute == 2:
            forte_percent = self.task.calculate_color_percentage(phoebe_star_blue_color, box)
            self.logger.debug(f'middle_star_blue_percent {forte_percent}')
            if forte_percent > 0.25:
                self.star_available = True
                return True
        return False

    def decide_teammate(self):
        from src.char.Zani import Zani
        from src.char.Cartethyia import Cartethyia
        from src.char.HavocRover import HavocRover

        self.char_rover = self.task.has_char(HavocRover)
        if char := self.task.has_char(Zani):
            self.char_zani = char
            self.attribute = 2
            self._zanfei_guang = bool(self.char_rover)
        elif self.task.has_char(Cartethyia) and self.char_rover:
            self.attribute = 2
            self._zanfei_guang = False
        else:
            self.attribute = 1
            self._zanfei_guang = False
        self.logger.debug(
            f"set attribute: {('support' if self.attribute == 2 else 'attacker')} zanfei={self._zanfei_guang}"
        )

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
            f"state_liberation {self.state['liberation']} state_starflash_combo {self.state['starflash_combo']}"
        )
        need_starflash = 1 if self._zanfei_guang else 2
        if self.state["liberation"] >= 1 and self.state["starflash_combo"] >= need_starflash:
            return True
        return False

    def reset_action(self):
        if self.attribute == 2:
            self.logger.info('reset action')
            self.state = {
                "enter_status": 0,
                "starflash_combo": 0,
                "liberation": 0,
                "outro": 0,
                "priority_liberation_cast": 0
            }

    def is_forte_full(self):
        if not self.star_available:
            return super().is_forte_full()
        return self.is_mouse_forte_full()

    def shorekeeper_auto_dodge(self):
        from src.char.ShoreKeeper import ShoreKeeper
        for i, char in enumerate(self.task.chars):
            if isinstance(char, ShoreKeeper):
                return char.auto_dodge(condition = self.flying)
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

phoebe_star_light_color = {
    'r': (235, 255),  # Red range
    'g': (220, 250),  # Green range
    'b': (160, 190)  # Blue range
}

phoebe_star_blue_color = {
    'r': (240, 255),  # Red range
    'g': (240, 255),  # Green range
    'b': (240, 255)  # Blue range
}
