import time
from decimal import Decimal, ROUND_UP, ROUND_HALF_UP
from enum import Enum
from typing import Callable
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

    def reset_state(self):
        self.char_phoebe = None
        self.blazes_threshold = -1
        self.chair_time = -1
        super().reset_state()

    def do_perform(self):
        if self.blazes_threshold == -1:
            self.decide_teammate()

        # 等待落地/入场动画，click=False 避免打出无意义普攻
        self.wait_down()
        self.check_liber()

        # 大招状态（branch 0）：保留基线 nightfall/liber2 逻辑
        if self.in_liberation:
            self.logger.info('in liberation')
            self.state = 1
            if self.should_end_liberation():
                self.click_liber2()
            else:
                self.nightfall_combo()
            return self.switch_next_char()

        self.state = 0
        self.f_break()
        self.crisis_time = -1  # 清除上轮可能遗留的过期计时

        # 读屏：焰光、forte 状态、E 图标亮度、大招可用性（缓存一次，全程使用）
        self.update_blazes()
        forte_full = self.is_e_forte_full()
        e_available = self.current_resonance() > 0.05
        liber_avail = self.liberation_available()
        if self.has_intro and self.blazes >= 1 and not liber_avail:
            self.sleep(0.2, check_combat=False)
            liber_avail = self.liberation_available()
            e_available = self.current_resonance() > 0.05
        predicted = float(self.blazes) + 0.1

        self.logger.info(
            f'Zani entry: blazes={self.blazes} threshold={self.blazes_threshold} '
            f'forte_full={forte_full} e_avail={e_available} predicted={predicted:.2f} '
            f'liber_avail={liber_avail} has_intro={self.has_intro}'
        )

        # 场景3：焰光拉满（1.0）且大招可用 → 直接开大
        # 0.96 can appear for both full and not-full bars; only 1.00 is safe for direct liberation.
        if self.blazes >= 1 and liber_avail:
            self.logger.info('scene3: blazes full, liberation available, direct liberation')
            if not self._try_liberation():
                self.sleep(0.1)
                self._try_liberation()
            return self.switch_next_char()

        # scene4: enhanced E ready; cast once, then liberate if needed.
        if forte_full:
            self.logger.info(f'scene4: enhanced E ready, predicted={predicted:.2f}')
            should_liberate = predicted >= self.blazes_threshold
            success = self.crisis_response_protocol_combo()
            if success and should_liberate and self.liberation_available():
                self.logger.info('scene4: enhanced E -> liberate')
                self._try_liberation(wait_crisis=True)
            else:
                self.logger.info('scene4: enhanced E -> switch')
            return self.switch_next_char()

        # 场景1：普通E 可用，焰光未满 → 完全沿用基线 crisis_response_protocol_combo
        # 内部已包含：E → 持续普攻/蓄力攒 forte → 强化E命中，不再需要自定义 E+一次普攻的写死序列
        if e_available:
            self.logger.info(f'scene1: normal E available, predicted={predicted:.2f}')
            success = self.crisis_response_protocol_combo()
            # combo 结束后即时检查一次大招。
            if success and self.blazes >= self.blazes_threshold:
                if self.liberation_available():
                    self.logger.info('scene1: liberate after enhanced E')
                    self._try_liberation(wait_crisis=True)
            return self.switch_next_char()

        # 场景2：E 在 CD → 普攻直到可切人
        self.logger.info('scene2: E on CD, normal attack until can switch')
        self.normal_attack_until_can_switch()
        return self.switch_next_char()

    # ─── 新增辅助方法 ───────────────────────────────────────────────
    def _try_liberation(self, wait_crisis=False):
        if wait_crisis:
            self.wait_crisis_protocol_end()
            self.update_blazes()
        if self.echo_available():
            self.click_echo(time_out=0)
        if self.click_liberation(send_click=True):
            self._liberation_followup()
            return True
        return False

    def _liberation_followup(self):
        """click_liberation 成功后进入大招态的固定收尾序列。"""
        self.crisis_time = -1
        self.state = 1
        self.in_liberation = True
        self.liberation_time = time.time()
        self.check_liber()
        self.continues_right_click(0.05)
        self.continues_normal_attack(0.15)
        self.nightfall_combo(cancel_last_smash=True)
        self.sleep(0.1)
        if self.is_mouse_forte_full():
            self.nightfall_combo()

    # ─── 基线方法（原样保留）──────────────────────────────────────────

    def basic_attack_breakthrough_combo(self):
        if self.is_e_forte_full():
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

    def should_end_liberation(self, time_only=False):
        if self.liberation_time_left() < 1.7:
            self.logger.info('Liberation is about to end, perform liberation2')
            return True
        if time_only or self.is_nightfall_ready():
            return False
        if self.wait_resonance_not_gray(send_click=True, liber_time_check=True) == State.INTERRUPTED:
            self.logger.info('Nightfall interrupted, perform liberation2')
            return True
        if not self.is_mouse_forte_full():
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
        if self.is_e_forte_full():
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
        self.logger.info('perform crisis_response_protocol')
        self.check_combat()
        if not self.is_e_forte_full():
            for _ in range(1):
                if (result := self.basic_attack_breakthrough()) != State.DONE:
                    break
                if (result := self.wait_forte_full(2.2, check_forte=True)) != State.DONE:
                    break
                else:
                    self.continues_right_click(0.05)
                    self.dodge_time = time.time()
            if result != State.FORTE_FULL and not self.is_e_forte_full():
                self.logger.info('crisis_response_protocol not FORTE_FULL')
                return False
        start = time.time()
        self.wait_until(lambda: not self.is_e_forte_full(), post_action=self.send_resonance_key, time_out=1)
        current = time.time()
        self.logger.debug(f'cast resonance duration {current - start}')
        if current - start < 0.35:
            self.logger.info(f'failed casting crisis_response_protocol, duration {current - start}')
            return False
        self.crisis_time = current
        return True

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
                    if gap < 0.01 and not self.is_e_forte_full():
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
            'condition': self.is_e_forte_full,
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

    def wait_until(self, condition: Callable, condition2: Callable = lambda: None,
                   post_action: Callable = lambda: None, time_out: float = 0, settle_time: float = 0):
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
        from src.char.Phoebe import Phoebe
        if char := self.task.has_char(Phoebe):
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
        if self.in_liberation:
            return SwitchPriority.MUST
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
    'r': (245, 255),
    'g': (245, 255),
    'b': (205, 225)
}

zani_blazes_color = {
    'r': (231, 257),
    'g': (239, 255),
    'b': (171, 201)
}

zani_forte_color = {
    'r': (239, 255),
    'g': (222, 255),
    'b': (156, 196)
}
