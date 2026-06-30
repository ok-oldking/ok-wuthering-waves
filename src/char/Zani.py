import time
from decimal import Decimal, ROUND_UP, ROUND_HALF_UP
from enum import Enum
import cv2
import numpy as np
import math

from src.char.BaseChar import BaseChar, SwitchPriority, forte_white_color
from ok import color_range_to_bound

class State(Enum):
    FORTE_FULL = 1
    CON_FULL = 2
    DONE = 3
    FAILED = 4
    INTERRUPTED = 5


class Zani(BaseChar):
    INTRO_READY_WAIT = 1.3
    AFTER_FIRST_E_WAIT = 0.08
    AFTER_NORMAL_WAIT = 0.12
    ENHANCED_E_READY_TIMEOUT = 2.5
    ENHANCED_E_POLL_INTERVAL = 0.03
    ENHANCED_E_READY_THRESHOLD = 0.05
    ENHANCED_E_READY_NO_FORTE_THRESHOLD = 0.16
    ENHANCED_E_READY_NO_FORTE_STABLE_POLLS = 2
    ENHANCED_E_SUCCESS_MIN_DURATION = 0.35
    LIBERATION_READY_TIMEOUT = 1.2
    FIRST_E_READY_TIMEOUT = 0.45
    FIRST_E_CONSUMED_TIMEOUT = 0.6
    FIRST_E_MAX_ATTEMPTS = 2
    NORMAL_ATTACK_RETRY_WAIT = 0.12
    POST_LIBER2_EA_WAIT = 0.10
    POST_LIBER2_SETTLE_WAIT = 0.12
    FIRST_E_CONSUMED_STABLE_POLLS = 2
    PRE_LIBERATION_ECHO_INTERVAL = 0.03

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.intro_motion_freeze_duration = 1.42
        self.liberation_time = 0
        self.in_liberation = False
        self.blazes = -1
        self.blazes_threshold = -1
        self.char_phoebe = None
        self.crisis_time = -1
        self.nightfall_time = -1
        self.state = 0
        self.chair_time = -1
        self.last_liber2 = -1
        self.dodge_time = -1
        self.attack_breakthrough_time = -1
        self.check_f_on_switch = False
        self.opening_liberation_done = False
        self.pending_post_liber2_ea = False

    def reset_state(self):
        self.char_phoebe = None
        self.blazes_threshold = -1
        self.chair_time = -1
        self.opening_liberation_done = False
        self.pending_post_liber2_ea = False
        super().reset_state()

    def _should_use_locked_phoebe_team_logic(self):
        has_phoebe = False
        has_shorekeeper = False
        for char in self.task.chars:
            if char is None:
                continue
            name = getattr(char, "char_name", "")
            cls_name = char.__class__.__name__
            if name == "char_phoebe" or cls_name == "Phoebe":
                has_phoebe = True
            elif name == "char_shorekeeper" or cls_name == "ShoreKeeper":
                has_shorekeeper = True
        return has_phoebe and has_shorekeeper

    def _find_phoebe_char(self):
        for char in self.task.chars:
            if char is None:
                continue
            name = getattr(char, "char_name", "")
            cls_name = char.__class__.__name__
            if name == "char_phoebe" or cls_name == "Phoebe":
                return char
        return None

    def _is_current_intro_from_phoebe(self):
        if not (self.has_intro and self.has_sub_dps_intro):
            return False
        if self.char_phoebe is None:
            return False
        return self.check_outro() == self.char_phoebe.char_name

    def _is_phoebe_char(self, char):
        if char is None:
            return False
        if self.char_phoebe is not None and char == self.char_phoebe:
            return True
        return (
            getattr(char, "char_name", None) == "char_phoebe"
            or char.__class__.__name__ == "Phoebe"
        )

    def _should_resume_liberation_immediately(self):
        return bool(
            self.in_liberation
            or self.state == 1
            or self.liberation_time_left() > 0
        )

    def _press_resonance_raw(self, reason):
        self.logger.info(f"Zani custom press {reason}")
        self.record_resonance_use()
        self.send_resonance_key()
        self.task.next_frame()

    def _resonance_icon_ready(self):
        return (
            self.current_resonance() > self.ENHANCED_E_READY_THRESHOLD
            and not self.has_cd('resonance')
        )

    def _wait_first_e_ready(self):
        start = time.time()
        last_percent = 0
        last_cd = True
        while time.time() - start < self.FIRST_E_READY_TIMEOUT:
            last_percent = self.current_resonance()
            last_cd = self.has_cd("resonance")
            if self._resonance_icon_ready():
                self.logger.info(
                    f"Zani custom first E ready percent {last_percent:.3f} cd {last_cd}"
                )
                return True
            self.sleep(self.ENHANCED_E_POLL_INTERVAL, check_combat=False)
            self.task.next_frame()
        self.logger.info(
            f"Zani custom first E not ready percent {last_percent:.3f} cd {last_cd}"
        )
        return False

    def _wait_first_e_consumed(self):
        start = time.time()
        last_percent = 0
        last_cd = False
        stable_consumed_polls = 0
        while time.time() - start < self.FIRST_E_CONSUMED_TIMEOUT:
            last_percent = self.current_resonance()
            last_cd = self.has_cd("resonance")
            if last_cd or last_percent <= 0.035:
                stable_consumed_polls += 1
            else:
                stable_consumed_polls = 0
            if stable_consumed_polls >= self.FIRST_E_CONSUMED_STABLE_POLLS:
                self.logger.info(
                    f"Zani custom first E consumed percent {last_percent:.3f} "
                    f"cd {last_cd} stable {stable_consumed_polls}"
                )
                return True
            self.sleep(self.ENHANCED_E_POLL_INTERVAL, check_combat=False)
            self.task.next_frame()
        self.logger.info(
            f"Zani custom first E not consumed percent {last_percent:.3f} "
            f"cd {last_cd} stable {stable_consumed_polls}"
        )
        return False

    def _cast_first_e_clean(self):
        if not self._wait_first_e_ready():
            return False
        for attempt in range(1, self.FIRST_E_MAX_ATTEMPTS + 1):
            self._press_resonance_raw(f"first E attempt {attempt}")
            if self._wait_first_e_consumed():
                return True
            if not self._resonance_icon_ready():
                return False
        return False

    def _wait_enhanced_e_icon(self):
        self.sleep(self.AFTER_NORMAL_WAIT, check_combat=False)
        start = time.time()
        last_percent = 0
        last_cd = True
        last_forte = False
        stable_ready_polls = 0
        while time.time() - start < self.ENHANCED_E_READY_TIMEOUT:
            last_percent = self.current_resonance()
            last_cd = self.has_cd("resonance")
            last_forte = self.is_forte_full()
            forte_ready = (
                last_forte
                and last_percent > self.ENHANCED_E_READY_THRESHOLD
                and not last_cd
            )
            no_forte_ready = (
                not last_forte
                and last_percent > self.ENHANCED_E_READY_NO_FORTE_THRESHOLD
                and not last_cd
            )
            if forte_ready:
                self.logger.info(
                    f"Zani custom enhanced E ready percent {last_percent:.3f} "
                    f"cd {last_cd} forte {last_forte}"
                )
                return True
            if no_forte_ready:
                stable_ready_polls += 1
                if stable_ready_polls >= self.ENHANCED_E_READY_NO_FORTE_STABLE_POLLS:
                    self.logger.info(
                        f"Zani custom enhanced E ready without forte percent {last_percent:.3f} "
                        f"cd {last_cd} stable {stable_ready_polls}"
                    )
                    return True
            else:
                stable_ready_polls = 0
            self.sleep(self.ENHANCED_E_POLL_INTERVAL, check_combat=False)
            self.task.next_frame()
        self.logger.info(
            f"Zani custom enhanced E timeout percent {last_percent:.3f} "
            f"cd {last_cd} forte {last_forte} stable {stable_ready_polls}"
        )
        return False

    def _cast_enhanced_e_full(self):
        self.logger.info("Zani custom cast enhanced E full")
        start = time.time()
        self.record_resonance_use()
        consumed = self.wait_until(
            lambda: not self.is_forte_full(),
            post_action=self.send_resonance_key,
            time_out=1
        )
        duration = time.time() - start
        if not consumed and duration < self.ENHANCED_E_SUCCESS_MIN_DURATION:
            self.logger.info(f"Zani custom failed casting enhanced E, duration {duration}")
            return False
        self.crisis_time = time.time()
        return True

    def _pre_liberation_e_a_enhanced_e(self, reason, wait_intro_window=False):
        self.logger.info(f"Zani custom pre liberation route {reason}")
        if wait_intro_window and self.INTRO_READY_WAIT > 0:
            self.sleep(self.INTRO_READY_WAIT, check_combat=False)

        if not self._cast_first_e_clean():
            return False
        self.sleep(self.AFTER_FIRST_E_WAIT, check_combat=False)

        self.logger.info("Zani custom normal attack once")
        self.task.click()

        if not self._wait_enhanced_e_icon():
            if self.has_cd("resonance") and not self.is_forte_full():
                self.logger.info("Zani custom retry normal attack for enhanced E window")
                self.sleep(self.NORMAL_ATTACK_RETRY_WAIT, check_combat=False)
                self.task.click()
                if not self._wait_enhanced_e_icon():
                    return False
            else:
                return False
        if self._cast_enhanced_e_full():
            return True
        if self.is_forte_full():
            self.logger.info("Zani custom retry enhanced E after brief settle")
            self.sleep(0.1, check_combat=False)
            return self._cast_enhanced_e_full()
        return False

    def _fast_phoebe_intro_pre_liberation(self):
        return self._pre_liberation_e_a_enhanced_e(
            'phoebe intro',
            wait_intro_window=True
        )

    def _wait_direct_enhanced_e_icon(self):
        start = time.time()
        last_percent = 0
        last_cd = True
        last_forte = False
        stable_ready_polls = 0
        while time.time() - start < self.ENHANCED_E_READY_TIMEOUT:
            last_percent = self.current_resonance()
            last_cd = self.has_cd("resonance")
            last_forte = self.is_forte_full()
            forte_ready = (
                last_forte
                and last_percent > self.ENHANCED_E_READY_THRESHOLD
                and not last_cd
            )
            no_forte_ready = (
                not last_forte
                and last_percent > self.ENHANCED_E_READY_NO_FORTE_THRESHOLD
                and not last_cd
            )
            if forte_ready:
                self.logger.info(
                    f"Zani v5 direct enhanced E ready percent {last_percent:.3f} "
                    f"cd {last_cd} forte {last_forte}"
                )
                return True
            if no_forte_ready:
                stable_ready_polls += 1
                if stable_ready_polls >= self.ENHANCED_E_READY_NO_FORTE_STABLE_POLLS:
                    self.logger.info(
                        f"Zani v5 direct enhanced E ready without forte percent {last_percent:.3f} "
                        f"cd {last_cd} stable {stable_ready_polls}"
                    )
                    return True
            else:
                stable_ready_polls = 0
            self.sleep(self.ENHANCED_E_POLL_INTERVAL, check_combat=False)
            self.task.next_frame()
        self.logger.info(
            f"Zani v5 direct enhanced E timeout percent {last_percent:.3f} "
            f"cd {last_cd} forte {last_forte} stable {stable_ready_polls}"
        )
        return False

    def _post_liber2_ea_before_switch(self, reason):
        self.logger.info(f"Zani v5 post liber2 E+A {reason}")
        self.sleep(self.POST_LIBER2_SETTLE_WAIT, check_combat=False)
        if not self._cast_first_e_clean():
            self.pending_post_liber2_ea = False
            return False
        self.sleep(self.POST_LIBER2_EA_WAIT, check_combat=False)
        self.task.click()
        self.pending_post_liber2_ea = False
        return True

    def _fast_phoebe_intro_direct_enhanced_e(self):
        self.logger.info("Zani v5 phoebe intro direct enhanced E route")
        if self.INTRO_READY_WAIT > 0:
            self.sleep(self.INTRO_READY_WAIT, check_combat=False)
        if not self._wait_direct_enhanced_e_icon():
            return False
        return self._cast_enhanced_e_full()

    def _enter_liberation_followup(self):
        self.crisis_time = -1
        self.state = 1
        self.in_liberation = True
        self.liberation_time = time.time()
        self.opening_liberation_done = True
        self.check_liber()
        self.continues_right_click(0.05)
        self.continues_normal_attack(0.15)
        self.nightfall_combo(cancel_last_smash=True)
        self.sleep(0.1)
        if self.is_forte_full():
            self.nightfall_combo()
        return self.switch_next_char()

    def _resume_liberation_branch(self):
        self.check_liber()
        self.in_liberation = True
        self.state = 1
        self.logger.info("Zani custom resume liberation without intro delay")
        if self.should_end_liberation():
            self.click_liber2()
        else:
            self.nightfall_combo()
        return self.switch_next_char()

    def _click_liberation_after_enhanced_e(self):
        if self.crisis_time > 0:
            self.wait_crisis_protocol_end()
            self.crisis_time = -1

        self.update_blazes()
        if not self.is_prepared():
            self.logger.info("Zani custom liberation aborted: not prepared after enhanced E")
            return False

        if self.echo_available():
            self.logger.info("Zani v5 cast echo before liberation")
            self.click_echo(time_out=0)
            self.sleep(self.PRE_LIBERATION_ECHO_INTERVAL, check_combat=False)

        if self.click_liberation(wait_if_cd_ready=self.LIBERATION_READY_TIMEOUT):
            return True

        if self.crisis_time > 0:
            self.wait_crisis_protocol_end()
        self.update_blazes()
        if not self.is_prepared():
            self.logger.info("Zani custom liberation retry aborted: not prepared")
            return False
        if self.echo_available():
            self.logger.info("Zani v5 retry cast echo before liberation")
            self.click_echo(time_out=0)
            self.sleep(self.PRE_LIBERATION_ECHO_INTERVAL, check_combat=False)
        return self.click_liberation(wait_if_cd_ready=self.LIBERATION_READY_TIMEOUT)

    def _builtin_do_perform(self):
        if self.blazes_threshold == -1:
            self.decide_teammate()
        if self.has_intro:
            self.logger.info('has intro')
            self.continues_normal_attack(1.3)
        else:
            self.sleep(0.01)
        self.wait_down()
        self.check_liber()
        if self.in_liberation:
            self.logger.info('in liberation')
            self.state = 1
            if self.should_end_liberation():
                self.click_liber2()
            else:
                self.nightfall_combo()
            return self.switch_next_char()
        else:
            self.state = 0
            self.f_break()

        if self.echo_available():
            self.click_echo(time_out=0)

        cast_liberation = False
        if self.crisis_time > 0:
            if self.time_elapsed_accounting_for_freeze(self.crisis_time, intro_motion_freeze=True) < 2.45:
                self.wait_crisis_protocol_end()
                if self.crisis_time_left() > - 1 and self.liberation_available() and self.is_prepared():
                    cast_liberation = True
                else:
                    self.continues_normal_attack(0.25)
                    self.sleep(0.25)
            self.crisis_time = - 1

        if not cast_liberation:
            self.chair_time = -1
            if (not self.has_intro and
                not self.is_first_engage() and
                self.time_elapsed_accounting_for_freeze(self.last_liber2, intro_motion_freeze=True) >= 2.6
            ):
                if self.time_elapsed_accounting_for_freeze(self.attack_breakthrough_time, intro_motion_freeze=True) < 4:
                    self.continues_right_click(0.05)
                    self.dodge_time = time.time()
                else:
                    self.sleep(0.25)
                    self.continues_normal_attack(0.25)
                    self.chair_time = time.time()
                self.last_liber2 = -1
                self.attack_breakthrough_time = -1
            breakthrough_result = self.basic_attack_breakthrough_combo()
            if self.is_prepared():
                self.logger.info('is ready')
                if not self.has_cd('liberation'):
                    self.logger.info('liberation no cd')
                    result = 0
                    if breakthrough_result == State.DONE:
                        result = self.wait_forte_full(2.2, check_forte=True)
                        if result == State.DONE:
                            self.continues_right_click(0.05)
                            self.dodge_time = time.time()
                    if breakthrough_result == State.INTERRUPTED or result == State.INTERRUPTED:
                        self.wait_until(lambda: not self.flying(), time_out=0.6)
                    if self.crisis_response_protocol_combo():
                        cast_liberation = self.liberation_available()
                else:
                    self.logger.info('liberation has cd')
                    if self.is_forte_full() and self.crisis_response_protocol_combo():
                        cast_liberation = self.liberation_available()
                self.logger.info(f'cast_liberation {cast_liberation}')
                if cast_liberation:
                    if self.blazes != 1:
                        self.wait_crisis_protocol_end()
                        self.crisis_time = - 1
                else:
                    return self.switch_next_char()

        if cast_liberation:
            self.check_combat()
            self.update_blazes()
            if self.click_liberation():
                self.crisis_time = - 1
                self.state = 1
                self.in_liberation = True
                self.liberation_time = time.time()
                self.check_liber()
                self.continues_right_click(0.05)
                self.continues_normal_attack(0.15)
                self.nightfall_combo(cancel_last_smash=True)
                self.sleep(0.1)
                if self.is_forte_full():
                    self.nightfall_combo()
            return self.switch_next_char()

        if self.is_forte_full():
            self.crisis_response_protocol_combo()
        self.switch_next_char()

    def do_perform(self):
        if not self._should_use_locked_phoebe_team_logic():
            self.logger.info("Zani custom exact fallback to current builtin")
            return self._builtin_do_perform()

        if self.blazes_threshold == -1:
            self.decide_teammate()

        if self.pending_post_liber2_ea and not self.in_liberation and self.liberation_time_left() <= 0:
            self._post_liber2_ea_before_switch("before perform")

        if self._should_resume_liberation_immediately():
            return self._resume_liberation_branch()

        if self._is_current_intro_from_phoebe():
            if not self.opening_liberation_done:
                if not self._fast_phoebe_intro_pre_liberation():
                    self.logger.info("Zani v5 first phoebe intro route failed, fallback builtin")
                    return self._builtin_do_perform()
            else:
                if not self._fast_phoebe_intro_direct_enhanced_e():
                    self.logger.info("Zani v5 direct enhanced E intro route failed, fallback builtin")
                    return self._builtin_do_perform()

            self.check_liber()
            if self.in_liberation:
                return self._resume_liberation_branch()

            self.update_blazes()
            if not self.is_prepared():
                self.logger.info("Zani v5 phoebe intro route aborted: not prepared")
                return self._builtin_do_perform()

            if self._click_liberation_after_enhanced_e():
                return self._enter_liberation_followup()

            self.logger.info("Zani v5 phoebe intro route liberation failed, fallback builtin")
            return self._builtin_do_perform()

        self.update_blazes()
        if (
            not self.opening_liberation_done
            and self.is_prepared()
            and not self.has_cd('liberation')
            and not self.check_liber()
        ):
            if not self._pre_liberation_e_a_enhanced_e(
                'ready before builtin',
                wait_intro_window=self.has_intro
            ):
                self.logger.info("Zani custom pre liberation route failed before builtin")
                return self._builtin_do_perform()

            self.update_blazes()
            if self.is_prepared() and self._click_liberation_after_enhanced_e():
                return self._enter_liberation_followup()

            self.logger.info("Zani custom pre liberation route did not open liberation")
            return self._builtin_do_perform()

        return self._builtin_do_perform()

    def basic_attack_breakthrough_combo(self):
        if self.is_forte_full():
            return State.FORTE_FULL
        self.logger.info('basic attack - breakthrough')
        if (result := self.basic_attack_breakthrough()) != State.DONE:
            return result
        self.attack_breakthrough_time = time.time()
        return State.DONE

    def click_liber2(self):
        start = time.time()
        self.task.in_liberation = True
        send_key = True
        not_liber_box = self.task.box_of_screen_scaled(2560, 1440, 1909, 1274, 1957, 1322, name='zani_not_liber_box', hcenter=True)
        while not self.task.find_one('box_target_enemy_inner', box=not_liber_box, threshold=0.75):
            if time.time() - start > 6:
                self.task.in_liberation = False
                if not self.check_liber():
                    self.update_blazes()
                return
            if self.current_resonance() == 0:
                start = time.time()
            elif time.time() - start > 1.5:
                send_key = False
            if send_key:
                self.send_liberation_key()
            self.task.next_frame()
        self.task.in_liberation = False
        current = time.time()
        duration = 2.25
        if current - start >= duration:
            self.last_liber2 = current
            self.add_freeze_duration(current - duration, duration, 0)
            self.logger.info('clicked liber2')
        self.in_liberation = False
        self.blazes = -1
        self.liberation_time = -1
        self.state = 0
        if self._should_use_locked_phoebe_team_logic():
            if not self._post_liber2_ea_before_switch("after liber2"):
                self.pending_post_liber2_ea = True

    def should_end_liberation(self, time_only=False):
        if self.liberation_time_left() < 1.7:
            self.logger.info('Liberation is about to end, perform liberation2')
            return True
        if time_only or self.is_nightfall_ready():
            return False
        if self.wait_resonance_not_gray(send_click=True, liber_time_check=True) == State.INTERRUPTED:
            self.logger.info('Nightfall interrupted, perform liberation2')
            return True
        if not self.is_forte_full():
            self.logger.info('Cannot perform another nightfall, perform liberation2')
            return True
        return False

    def liberation_time_left(self):
        if not self.in_liberation or self.liberation_time <= 0:
            return 0
        result = 20 - self.time_elapsed_accounting_for_freeze(self.liberation_time)
        self.logger.debug(f'liberation_lasted: {result}')
        return result

    def nightfall_combo(self, cancel_last_smash=False):
        self.logger.info('perform nightfall_combo')
        start = time.time()
        if not self.is_nightfall_ready():
            while not self.is_nightfall_ready() or time.time() - start < 1.6:
                self.click()
                if time.time() - start > 3.5 or not self.in_liberation:
                    return
                if self.should_end_liberation(time_only=True) and self.click_liber2():
                    return
                self.check_combat()
                self.task.next_frame()
        self.continues_normal_attack(0.5)
        if cancel_last_smash:
            self.logger.info('cancel nightfall last smash')
            start = time.time()
            while self.is_nightfall_ready(threshold=0.035):
                if time.time() - start > 2.5:
                    break
                self.click()
                self.task.next_frame()
            self.sleep(0.25, check_combat=False)
            self.continues_right_click(0.1)
        else:
            self.nightfall_time = time.time()

    def is_nightfall_ready(self, threshold=0.15):
        box = self.task.box_of_screen_scaled(2560, 1440, 1853, 1233, 1964, 1344, name='zani_attack', hcenter=True)
        self.task.draw_boxes(box.name, box)
        light_percent = self.calculate_color_percentage_in_masked(zani_light_color, box, 0.425, 0.490)
        self.logger.debug(f'nightfall_percent {light_percent}')
        if light_percent > threshold:
            return True
        return False

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
    
    def nightfall_time_left(self):
        if self.nightfall_time <= 0:
            return 0
        result = 2.2 - self.time_elapsed_accounting_for_freeze(self.nightfall_time, intro_motion_freeze=True)
        if self.nightfall_time <= 0:
            self.nightfall_time = -1
            return 0
        self.logger.debug(f'nightfall_time_left: {result}')
        return result

    def standard_defense_protocol_combo(self):
        if self.is_forte_full():
            return State.FORTE_FULL
        if self.resonance_available():
            self.logger.info('perform standard_defense_protocol')
            self.click_resonance(send_click=False)
            self.sleep(0.2)
            self.continues_normal_attack(0.2)
            return State.DONE
        return State.FAILED

    def basic_attack_breakthrough(self):
        wait_chair = 1.2
        if self.chair_time == -1:
            result = self.standard_defense_protocol_combo()
            if result == State.FAILED:
                sleep = 0.3 - (time.time() - self.dodge_time)
                if (result := self.wait_forte_full(sleep)) != State.DONE:
                    return result
                self.task.mouse_down()
                if (result := self.wait_forte_full(0.6)) != State.DONE:
                    return result
                self.task.mouse_up()
                wait_chair = 1.15
                if (result := self.wait_forte_full(0.85, send_click=True)) != State.DONE:
                    return result
            elif result == State.FORTE_FULL:
                return State.FORTE_FULL
        else:
            wait_chair -= (time.time() - self.chair_time)
            self.chair_time = -1
        if (result := self.wait_forte_full(wait_chair)) != State.DONE:
            return result
        self.continues_normal_attack(0.2)
        return result

    def crisis_response_protocol_combo(self):
        if not self._should_use_locked_phoebe_team_logic():
            self.logger.info('perform crisis_response_protocol')
            self.check_combat()
            if not self.is_forte_full():
                result = State.DONE
                for _ in range(1):
                    if (result := self.basic_attack_breakthrough()) != State.DONE:
                        break
                    if (result := self.wait_forte_full(2.2, check_forte=True)) != State.DONE:
                        break
                    else:
                        self.continues_right_click(0.05)
                        self.dodge_time = time.time()
                if result != State.FORTE_FULL and not self.is_forte_full():
                    self.logger.info('crisis_response_protocol not FORTE_FULL')
                    return False
            start = time.time()
            self.wait_until(lambda: not self.is_forte_full(), post_action=self.send_resonance_key, time_out=1)
            current = time.time()
            self.logger.debug(f'cast resonance duration {current - start}')
            if current - start < 0.35:
                self.logger.info(f'failed casting crisis_response_protocol, duration {current - start}')
                return False
            self.crisis_time = current
            return True
        return self._pre_liberation_e_a_enhanced_e(
            'builtin crisis response',
            wait_intro_window=False
        )

    def get_forte(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 1628, 1997, 2183, 2003, name='zani_forte', hcenter=True)
        self.task.draw_boxes(box.name, box)
        forte_percent = self.task.calculate_color_percentage(zani_forte_color, box)
        forte_percent = Decimal(str(forte_percent)).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
        self.logger.debug(f'forte_percent {forte_percent}')
        return forte_percent

    def check_forte_action(self):
        last_check_time = [0]
        last_value = [-1]
        started_checking = [False]

        def pre_action():
            current_time = time.time()
            elapsed = current_time - start_time[0]
            if elapsed > 0.8:
                started_checking[0] = True
            if not started_checking[0]:
                return False
            if current_time - last_check_time[0] >= 0.2:
                current_value = self.get_forte()
                if last_value[0] > 0:
                    gap = current_value - last_value[0]
                    self.logger.info(f"check_forte gap: {gap} current_value: {current_value}")
                    if gap < 0.01 and not self.is_forte_full():
                        self.continues_right_click(0.05)
                        self.dodge_time = time.time()
                        return True
                last_value[0] = current_value
                last_check_time[0] = current_time
            return False

        start_time = [time.time()]
        return pre_action

    def wait_forte_full(self, timeout=1, send_click=False, check_forte=False, settle_time=0) -> State:
        if timeout <= 0:
            return State.DONE
        kwargs = {
            'condition': self.is_forte_full,
            'condition2': self.flying,
            'time_out': timeout,
            'settle_time': settle_time
        }
        if send_click:
            kwargs['post_action'] = self.click_with_interval
        if check_forte:
            pre_action_fn = self.check_forte_action()
            kwargs['condition2'] = lambda: self.flying() or pre_action_fn()
        result = self.wait_until(**kwargs)
        if result == State.INTERRUPTED:
            pass
        elif result:
            result = State.FORTE_FULL
        else:
            result = State.DONE
        return result

    def wait_until(self, condition: callable, condition2: callable = lambda: None,
                   post_action: callable = lambda: None, time_out: float = 0, settle_time: float = 0):
        if time_out <= 0:
            return False
        start = time.time()
        stable_start = None
        once = True
        while time.time() - start < time_out:
            if condition():
                if settle_time == 0:
                    return True
                if stable_start is None:
                    stable_start = time.time()
                elif time.time() - stable_start >= settle_time:
                    return True
            else:
                stable_start = None
            if condition2():
                return State.INTERRUPTED
            if once:
                self.check_combat()
                once = False
            post_action()
            self.task.next_frame()
        return False

    def is_forte_full(self):
        if self.in_liberation:
            box = self.task.box_of_screen_scaled(2560, 1440, 1527, 1335, 1544, 1352, name='forte_full', hcenter=True)
        else:
            box = self.task.box_of_screen_scaled(3840, 2160, 2284, 1992, 2311, 2019, name='forte_full', hcenter=True)
        self.task.draw_boxes(box.name, box)
        mean_val = contrast_val = 0
        if self.task.calculate_color_percentage(forte_white_color, box) > 0.08:
            cropped = box.crop_frame(self.task.frame)
            gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
            mean_val = np.mean(gray)
            contrast_val = np.std(gray)
            self.logger.debug(f'is_forte_full mean {mean_val} contrast {contrast_val}')
        return mean_val > 200 and contrast_val > 40

    def crisis_time_left(self):
        if self.crisis_time <= 0:
            return 0
        result = 1.6 - self.time_elapsed_accounting_for_freeze(self.crisis_time, intro_motion_freeze=True)
        self.logger.debug(f'crisis_time_left: {result}')
        return result

    def wait_crisis_protocol_end(self):
        if self.crisis_time_left() <= 0:
            return State.DONE
        if self.last_res > 0 and self.time_elapsed_accounting_for_freeze(self.last_res) < 5:
            self.wait_until(lambda: self.crisis_time_left() <= 0, time_out=2)
        else:
            self.wait_resonance_not_gray()

    def decide_teammate(self):
        if char := self._find_phoebe_char():
            self.char_phoebe = char
            self.blazes_threshold = 0.6
        else:
            self.blazes_threshold = 0.4

    def update_blazes(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 1627, 2014, 2176, 2017, name='zani_blazes', hcenter=True)
        blazes_percent = self.task.calculate_color_percentage(zani_blazes_color, box)
        blazes_percent = Decimal(str(blazes_percent)).quantize(Decimal('0.01'), rounding=ROUND_UP)
        self.blazes = blazes_percent
        self.logger.debug(f'blazes_percent {blazes_percent}')

    def is_prepared(self):
        if self.is_current_char:
            self.update_blazes()
        if self.blazes >= self.blazes_threshold:
            return True
        if (self.char_phoebe is not None and
                self.char_phoebe.state["outro"] >= 1 and
                self.blazes >= 0.4
        ):
            return True
        return False

    def wait_resonance_not_gray(self, send_click=False, liber_time_check=False, timeout=2.5):
        kwargs = {
            'condition': lambda: self.current_resonance() != 0,
            'time_out': timeout,
            'settle_time': 0.1
        }
        if send_click:
            kwargs['post_action'] = self.click_with_interval
        if liber_time_check:
            kwargs['condition2'] = lambda: self.liberation_time_left() < 1.7
        self.wait_until(**kwargs)

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if not self._should_use_locked_phoebe_team_logic():
            if self.in_liberation:
                return SwitchPriority.MUST
            if has_intro and self.crisis_time_left() > 0:
                return SwitchPriority.NO
            return super().get_switch_priority(current_char, has_intro, target_low_con)
        if self.in_liberation:
            return SwitchPriority.MUST
        if self._is_phoebe_char(current_char) and not has_intro:
            self.logger.info("Zani custom block Phoebe non-intro switch-in")
            return SwitchPriority.NO
        if has_intro and self.crisis_time_left() > 0:
            return SwitchPriority.NO
        return super().get_switch_priority(current_char, has_intro, target_low_con)

    def wait_switch(self):
        if self.has_intro and self.nightfall_time_left() > 0:
            self.logger.debug(f'has_intro {self.has_intro}, wait nightfall end')
            if self.nightfall_time_left() > 0 and self.liberation_time_left() >= 2:
                return True
        return False

    def check_liber(self):
        if not self.task.in_team_and_world():
            return self.in_liberation
        not_liber_box = self.task.box_of_screen_scaled(2560, 1440, 1909, 1274, 1957, 1322, name='zani_not_liber_box', hcenter=True)
        liber_box = self.task.box_of_screen_scaled(2560, 1440, 1779, 1273, 1830, 1322, name='zani_liber_box', hcenter=True)
        if self.task.find_one('box_target_enemy_inner', box=not_liber_box, threshold=0.75):
            self.in_liberation = False
        elif self.task.find_one('box_target_enemy_inner', box=liber_box, threshold=0.75):
            self.in_liberation = True
        return self.in_liberation

    def get_state(self):
        if self.state == 1 and self.liberation_time_left() <= 0:
            self.blazes = -1
            self.state = 0
        return self.state


zani_light_color = {
    'r': (245, 255),  # Red range
    'g': (245, 255),  # Green range
    'b': (205, 225)  # Blue range
}

zani_blazes_color = {
    'r': (231, 257),  # Red range
    'g': (239, 255),  # Green range
    'b': (171, 201)  # Blue range
}

zani_forte_color = {
    'r': (239, 255),  # Red range
    'g': (222, 255),  # Green range
    'b': (156, 196)  # Blue range
}
