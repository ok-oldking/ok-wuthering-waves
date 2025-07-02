import time
from decimal import Decimal, ROUND_UP, ROUND_HALF_UP
from enum import Enum
import cv2
import numpy as np

from src.char.BaseChar import BaseChar, Priority, text_white_color, forte_white_color
from src.combat.CombatCheck import aim_color


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

    def reset_state(self):
        self.char_phoebe = None
        self.blazes_threshold = -1
        self.chair_time = -1
        super().reset_state()

    def count_forte_priority(self):
        return 1

    def current_attack(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 2709, 1894, 2827, 1972, name='box_attack', hcenter=True)
        self.task.draw_boxes(box.name, box)
        return self.task.calculate_color_percentage(text_white_color, box)

    def do_perform(self):
        if self.blazes_threshold == -1:
            self.decide_teammate()
        if self.has_intro:
            self.logger.info(f'has intro')
            self.continues_normal_attack(1.3)
        else:
            self.sleep(0.01)
        self.wait_down()
        self.check_liber()
        if self.in_liberation:
            self.logger.info(f'in liberation')
            self.state = 1
            if self.should_end_liberation():
                self.click_liber2()
            else:
                self.nightfall_combo()
            return self.switch_next_char()
        else:
            self.state = 0

        if self.echo_available():
            self.click_echo(time_out=0.1)

        cast_liberation = False
        if self.crisis_time > 0:
            if self.time_elapsed_accounting_for_freeze(self.crisis_time, intro_motion_freeze=True) < 2.45:
                self.wait_crisis_protocol_end()
                if self.crisis_time_left() > - 1 and self.liberation_available() and self.is_prepared():
                    cast_liberation = True
                else:
                    self.continues_normal_attack(0.1)
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
                    self.sleep(0.07)
                    self.continues_normal_attack(0.1)
                    self.chair_time = time.time()
                self.last_liber2 = -1
                self.attack_breakthrough_time = -1
            breakthrough_result = self.basic_attack_breakthrough_combo()
            if self.is_prepared():
                self.logger.info(f'is ready')
                if not self.has_cd('liberation'):
                    self.logger.info(f'liberation no cd')
                    result = 0
                    if breakthrough_result == State.DONE:
                        result = self.wait_forte_full(2.2, check_forte=True)
                        if result == State.DONE:
                            self.continues_right_click(0.05)
                            self.dodge_time = time.time()
                    if breakthrough_result == State.INTERRUPTED or result == State.INTERRUPTED:
                        self.wait_until(lambda: self.is_interrupted() == False, time_out=0.6)
                    if self.crisis_response_protocol_combo():
                        cast_liberation = self.liberation_available()
                else:
                    self.logger.info(f'liberation has cd')
                    if self.is_forte_full() and self.crisis_response_protocol_combo():
                        cast_liberation = self.liberation_available()
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

    def basic_attack_breakthrough_combo(self):
        if self.is_forte_full():
            return State.FORTE_FULL
        self.logger.info(f'basic attack - breakthrough')
        if self.chair_time == -1:
            if (result := self.basic_attack_breakthrough()) != State.DONE:
                return result
        else:
            wait_time = 1.1 - (time.time() - self.chair_time)
            self.logger.debug(f'breakthrough wait_time {wait_time}')
            if (result := self.wait_forte_full(wait_time)) != State.DONE:
                return result
            self.continues_normal_attack(0.1)
        self.attack_breakthrough_time = time.time()
        return State.DONE

    def click_liber2(self):
        start = time.time()
        self.task.in_liberation = True
        send_key = True
        inner_box = 'box_target_enemy_inner'
        while not self.task.find_one(inner_box, box=self.task.get_box_by_name(inner_box), threshold=0.75):
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
            self.logger.info(f'clicked liber2')
        self.in_liberation = False
        self.blazes = -1
        self.liberation_time = -1
        self.state = 0

    def should_end_liberation(self, time_only=False):
        if self.liberation_time_left() < 1.7:
            self.logger.info(f'Liberation is about to end, perform liberation2')
            return True
        if time_only or self.is_nightfall_ready():
            return False
        if self.wait_resonance_not_gray(send_click=True, liber_time_check=True) == State.INTERRUPTED:
            self.logger.info(f'Nightfall interrupted, perform liberation2')
            return True
        if not self.is_forte_full():
            self.logger.info(f'Cannot perform another nightfall, perform liberation2')
            return True
        return False

    def liberation_time_left(self):
        if not self.in_liberation or self.liberation_time <= 0:
            return 0
        result = 20 - self.time_elapsed_accounting_for_freeze(self.liberation_time)
        self.logger.debug(f'liberation_lasted: {result}')
        return result

    def nightfall_combo(self, cancel_last_smash=False):
        self.logger.info(f'perform nightfall_combo')
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
            self.logger.info(f'cancel nightfall last smash')
            start = time.time()
            while self.is_nightfall_ready(threshold=0.035):
                if time.time() - start > 2.5:
                    break
                self.click()
                self.task.next_frame()
            self.sleep(0.1, check_combat=False)
            self.continues_right_click(0.1)
        else:
            self.nightfall_time = time.time()

    def is_nightfall_ready(self, threshold=0.05):
        box = self.task.box_of_screen_scaled(3840, 2160, 2680, 1845, 2862, 2025, name='zani_attack', hcenter=True)
        light_percent = self.task.calculate_color_percentage(zani_light_color, box)
        self.logger.debug(f'nightfall_percent {light_percent}')
        if light_percent > threshold:
            return True
        return False

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
        if self.time_elapsed_accounting_for_freeze(self.last_res) >= self.res_cd and self.resonance_available():
            self.logger.info(f'perform standard_defense_protocol')
            self.send_resonance_key()
            self.update_res_cd()
            self.sleep(0.1)
            self.continues_normal_attack(0.1)
            return State.DONE
        return State.FAILED

    def basic_attack_breakthrough(self):
        result = self.standard_defense_protocol_combo()
        wait_chair = 1.25
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
        if (result := self.wait_forte_full(wait_chair)) != State.DONE:
            return result
        self.continues_normal_attack(0.1)
        return result

    def crisis_response_protocol_combo(self):
        self.logger.info(f'perform crisis_response_protocol')
        self.check_combat()
        if not self.is_forte_full():
            for _ in range(1):
                if (result := self.basic_attack_breakthrough()) != State.DONE:
                    break
                if (result := self.wait_forte_full(2.2, check_forte=True)) != State.DONE:
                    break
                else:
                    self.continues_right_click(0.05)
                    self.dodge_time = time.time()
            if result != State.FORTE_FULL and not self.is_forte_full():
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
            'condition2': self.is_interrupted,
            'time_out': timeout,
            'settle_time': settle_time
        }
        if send_click:
            kwargs['post_action'] = self.click_with_interval
        if check_forte:
            pre_action_fn = self.check_forte_action()
            kwargs['condition2'] = lambda: self.is_interrupted() or pre_action_fn()
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

    def is_interrupted(self):
        return (
                self.current_tool() < 0.15 and
                self.current_echo() < 0.15 and
                self.current_resonance() < 0.15
        )

    def is_forte_full(self):
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
        from src.char.Phoebe import Phoebe
        if char := self.task.has_char(Phoebe):
            self.char_phoebe = char
            self.blazes_threshold = 0.9
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

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if self.in_liberation:
            return Priority.MAX
        elif has_intro and self.crisis_time_left() > 0:
            return -10000
        else:
            return super().do_get_switch_priority(current_char, has_intro)

    def wait_switch(self):
        if self.has_intro and self.nightfall_time_left() > 0:
            self.logger.debug(f'has_intro {self.has_intro}, wait nightfall end')
            if self.nightfall_time_left() > 0 and self.liberation_time_left() >= 2:
                return True
        return False

    def check_liber(self):
        if not self.task.in_team_and_world():
            return self.in_liberation
        inner_box = 'box_target_enemy_inner'
        long_inner_box = 'box_target_enemy_long_inner'
        if self.task.find_one(inner_box, box=self.task.get_box_by_name(inner_box), threshold=0.75):
            self.in_liberation = False
        elif self.task.find_one(long_inner_box, box=self.task.get_box_by_name(long_inner_box), threshold=0.75):
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
