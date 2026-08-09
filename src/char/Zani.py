import time
from decimal import Decimal, ROUND_UP, ROUND_HALF_UP
from enum import Enum
from typing import Callable
import cv2
import numpy as np
import math
from src.char.BaseChar import BaseChar, CharType, SwitchPriority, forte_white_color
from ok import color_range_to_bound

class State(Enum):
    FORTE_FULL = 1
    CON_FULL = 2
    DONE = 3
    FAILED = 4
    INTERRUPTED = 5

class Zani(BaseChar):

    def _reset_zani_state(self):
        """共用状态重置：__init__ 与 reset_state 各字段保持一致。"""
        self.char_phoebe = None
        self.char_rover = None
        self.blazes_threshold = -1
        self.chair_time = -1
        self._zanfei_guang = False
        self._force_switch_me = False
        self.in_liberation = False
        self._liber_phase = 0
        self._liber_handoff_token = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.intro_motion_freeze_duration = 1.42
        self.liberation_time = 0
        self.blazes = -1
        self.crisis_time = -1
        self.nightfall_time = -1
        self.state = 0
        self.last_liber2 = -1
        self.dodge_time = -1
        self.attack_breakthrough_time = -1
        self.check_f_on_switch = False
        self._reset_zani_state()

    def reset_state(self):
        # 大招标记跨战斗清零：load_chars 复用实例残留 True 会把开场切人锁到赞妮
        self._reset_zani_state()
        super().reset_state()

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

    def switch_next_char(self, *args, **kwargs):
        # 仅赞菲守（无 Rover）需要 force 切回菲比；赞菲光走 runtime 默认
        if not self._zanfei_guang and self.is_con_full() and self.char_phoebe is not None:
            # 大招中满协奏切菲比发 insert token（菲比普攻 1.5s 后切回；R2 后退大不发→普通轮转）
            if self.in_liberation:
                self._liber_phase = 2
                self._liber_handoff_token += 1
                self.logger.info(f'zanfei: liber insert handoff phase=2 token={self._liber_handoff_token} default switch')
            return self._force_switch_to(self.char_phoebe)
        return super().switch_next_char(*args, **kwargs)

    def f_break(self, check_f_on_switch=False, force=False):
        """赞妮不做处决：f_break 在切人时 F+左键连打 0.5-5s，
        会打断赞妮开场动作（强化 E/夜闪）并可能触发处决动画导致 target lost。"""
        return False

    def do_perform(self):
        if self.blazes_threshold == -1:
            self.decide_teammate()
        # target lost 防护（非大招）：连续 3 轮无目标主动出战斗（runtime 每轮 3s 重试会永久站桩）
        if not self.in_liberation and not self.task.has_target():
            self._no_target_streak = getattr(self, '_no_target_streak', 0) + 1
            if self._no_target_streak >= 3:
                self._no_target_streak = 0
                self.logger.info('zanfei: no target 3 rounds, exit combat')
                self.task.raise_not_in_combat('zanfei no target 3 rounds')
            return
        self._no_target_streak = 0
        if self._zanfei_guang:
            return self._do_perform_zanfei()
        self.wait_down()
        self.check_liber()
        if self.in_liberation:
            self.state = 1
            if self.should_end_liberation():
                self.click_liber2()
            else:
                self.nightfall_combo()
            return self.switch_next_char()
        return self._non_liber_rotation(zanfei=False)

    def _sample_non_liber_rotation(self, reset_liber_phase=False):
        self.state = 0
        self.f_break()
        self.crisis_time = -1
        if reset_liber_phase:
            self._liber_phase = 0
        self.update_blazes()
        forte_full = self.is_e_forte_full()
        e_available = self.current_resonance() > 0.05
        liber_avail = self.liberation_available()
        if self.has_intro and self.blazes >= 1 and not liber_avail:
            self.sleep(0.2, check_combat=False)
            liber_avail = self.liberation_available()
            e_available = self.current_resonance() > 0.05
        return forte_full, e_available, liber_avail, float(self.blazes) + 0.1

    def _do_perform_zanfei(self):
        self.wait_down()
        self.check_liber()
        if self.in_liberation:
            self.state = 1
            return self._do_liber_zanfei()
        return self._non_liber_rotation(zanfei=True, reset_liber_phase=True)


    def _non_liber_rotation(self, zanfei=False, reset_liber_phase=False):
        """非大招轮换（赞菲守/赞菲光共用，沿用 do_perform 场景体系）。
        zanfei=True（赞菲光）：crisis 动作只作过渡（加焰光/等大招 CD），动作完直接开大——
        大招 CD 经验上已好，焰光不设门槛；成功内部已 handoff 切人，失败留场下轮再判。
        zanfei=False（赞菲守）：行为与原 do_perform 完全一致（焰光达标才开大，尝试后切走）。"""
        forte_full, e_available, liber_avail, predicted = self._sample_non_liber_rotation(
            reset_liber_phase=reset_liber_phase
        )
        # 场景3：有大（zanfei 光不看焰光；赞菲守需焰光满）→ 直接开大
        if (zanfei or self.blazes >= 1) and liber_avail:
            if not self._try_liberation(zanfei=zanfei):
                self.sleep(0.1)
                self._try_liberation(zanfei=zanfei)
            if zanfei:
                return
            return self.switch_next_char()
        if zanfei:
            # 赞菲光没大：crisis 动作作过渡（强化E图标在→scene4 快路径；否则→scene1 E+普攻）→ 动作完无条件开大
            if forte_full or e_available:
                self.crisis_response_protocol_combo()
                self._try_liberation(wait_crisis=True, zanfei=True)
                return
            # 场景2：E 在 CD → 普攻过渡后切走（菲比补协奏再入场）
            self.normal_attack_until_can_switch()
            return self.switch_next_char()
        # 场景4：强化E已就绪 → 蓄力后预测达标（一个强化E后能到阈值）则开大
        if forte_full:
            should_liberate = predicted >= self.blazes_threshold
            success = self.crisis_response_protocol_combo()
            if success and should_liberate and self.liberation_available():
                self._try_liberation(wait_crisis=True)
            return self.switch_next_char()
        # 场景1：普通E 可用，焰光未满 → crisis 蓄力（强化e）后达标则开大
        if e_available:
            success = self.crisis_response_protocol_combo()
            if success and self.blazes >= self.blazes_threshold:
                # liberation_available 找图失败时返回 None：视为可用尝试开大（失败无害）
                if self.liberation_available() is not False:
                    self._try_liberation(wait_crisis=True)
            return self.switch_next_char()
        # 场景2：E 在 CD → 普攻直到可切人
        self.normal_attack_until_can_switch()
        return self.switch_next_char()
    def _handoff_liber_insert(self, next_phase):
        """phase1/2 插队切人：不指定目标，默认 switch；落地角色靠 phase 跑 insert 短轴。"""
        self._liber_phase = next_phase
        self._liber_handoff_token += 1
        self.logger.info(f'zanfei: liber insert handoff phase={next_phase} token={self._liber_handoff_token} default switch')
        return self.switch_next_char()

    def consume_liber_handoff(self):
        """One-shot: only the character landing from this handoff runs the insert axis."""
        if self._liber_handoff_token <= 0:
            return False
        self._liber_handoff_token = 0
        return True

    def try_consume_insert_handoff(self):
        """Consume one insert handoff only while the liberation phase is live."""
        if not self.in_liberation or self._liber_phase not in (2, 3):
            return False
        return self.consume_liber_handoff()

    def _complete_liberation_to_phoebe(self, phase=4):
        self.click_liber2()
        self._liber_phase = phase
        return self._switch_to_phoebe_full()

    def _run_phase_three_liberation(self):
        if self.should_end_liberation():
            return self._complete_liberation_to_phoebe()
        self.nightfall_combo()
        while self.in_liberation and self._liber_phase == 3:
            if self.should_end_liberation():
                return self._complete_liberation_to_phoebe()
            if not self.is_mouse_forte_full() and not self.is_nightfall_ready():
                if self.should_end_liberation(time_only=False):
                    return self._complete_liberation_to_phoebe()
                self.continues_normal_attack(0.3)
                self.check_liber()
                if not self.in_liberation:
                    self._liber_phase = 0
                    return self.switch_next_char()
                continue
            self.nightfall_combo()
            self.check_liber()
            if not self.in_liberation:
                self._liber_phase = 0
                return self._switch_to_phoebe_full()
        return self.switch_next_char()

    def _do_liber_zanfei(self):
        """大招期间占位逻辑：phase1/2 默认切人插队，phase3 经典夜幕直到 R2。"""
        if self._liber_phase == 2:
            self.logger.info('zanfei liber phase2: nightfall then default insert handoff')
            if self.should_end_liberation():
                return self._complete_liberation_to_phoebe()
            self.nightfall_combo()
            return self._handoff_liber_insert(3)
        if self._liber_phase == 3:
            self.logger.info('zanfei liber phase3: stay until R2')
            return self._run_phase_three_liberation()
        if self.should_end_liberation():
            return self._complete_liberation_to_phoebe(phase=0)
        self.nightfall_combo()
        return self.switch_next_char()

    def _switch_to_phoebe_full(self):
        phoebe = self.char_phoebe
        if phoebe is None:
            from src.char.Phoebe import Phoebe
            phoebe = self.task.has_char(Phoebe)
            self.char_phoebe = phoebe
        if phoebe is None:
            return self.switch_next_char()
        self.logger.info('zanfei: force switch to Phoebe (full perform after R2)')
        phoebe.reset_action()
        self._liber_phase = 0
        return self._force_switch_to(phoebe)

    def _try_liberation(self, wait_crisis=False, zanfei=False):
        if wait_crisis:
            before_blazes = self.blazes
            self.wait_crisis_protocol_end()
            if zanfei:
                self.update_blazes()
            elif not self._wait_enhanced_e_commit(before_blazes):
                return False
        if self.echo_available():
            self.click_echo(time_out=0)
        if self.click_liberation(send_click=True):
            self._liberation_followup(zanfei=zanfei)
            return True
        return False

    def _wait_enhanced_e_commit(self, before_blazes):
        elapsed = self.time_elapsed_accounting_for_freeze(self.crisis_time, intro_motion_freeze=True) if self.crisis_time > 0 else -1
        if 0 <= elapsed < 2.0:
            self.wait_until(lambda : self.time_elapsed_accounting_for_freeze(self.crisis_time, intro_motion_freeze=True) >= 2.0, time_out=3.0)
            elapsed = self.time_elapsed_accounting_for_freeze(self.crisis_time, intro_motion_freeze=True)
        # 强化E命中结算延迟 2~6s：2.0s 首验未涨时轮询重验至 4.5s，焰光到账立即通过（有界不无限等）
        while self.blazes <= before_blazes and elapsed >= 2.0 and elapsed < 4.5:
            self.sleep(0.4)
            self.update_blazes()
            elapsed = self.time_elapsed_accounting_for_freeze(self.crisis_time, intro_motion_freeze=True)
        # committed 同时要求焰光增量：强化E未命中（blazes 不涨）不开大——crisis 命中必 +0.04 可检测
        committed = elapsed >= 2.0 and self.blazes > before_blazes
        self.logger.info(f'zani: enhanced E commit elapsed={elapsed:.2f}s blazes={before_blazes}->{self.blazes} committed={committed}')
        return committed

    def _start_liberation(self):
        self.crisis_time = -1
        self.state = 1
        self.in_liberation = True
        self.liberation_time = time.time()
        self.check_liber()
        self.continues_right_click(0.05)
        self.continues_normal_attack(0.15)

    def _liberation_followup(self, zanfei=False):
        self._start_liberation()
        if zanfei:
            self.nightfall_combo(cancel_last_smash=True, acquire_timeout=3.5, cancel_with_dodge=False)
            self._handoff_liber_insert(2)
            return
        self.nightfall_combo(cancel_last_smash=True)
        self.sleep(0.1)
        if self.is_mouse_forte_full():
            self.nightfall_combo()

    def basic_attack_breakthrough_combo(self):
        if self.is_e_forte_full():
            return State.FORTE_FULL
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
                # 默认已退大，仅当前帧明确显示仍在大招时 check_liber() 置回 True（避免保留旧值）
                self.in_liberation = False
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
        if self.liberation_time_left() < 1.0:
            self.logger.info('Liberation is about to end, perform liberation2')
            return True
        if time_only or self.is_nightfall_ready():
            return False
        if not self.is_mouse_forte_full():
            # 重击条未满站桩重读 1.0s（防提前 R2——0.5s 不够，1s 兜底）
            if not self.task.wait_until(self.is_mouse_forte_full, time_out=1.0, settle_time=0.1):
                self.logger.info('Cannot perform another nightfall, perform liberation2')
                return True
            return False
        return False


    def liberation_time_left(self):
        if not self.in_liberation or self.liberation_time <= 0:
            return 0
        result = 20 - self.time_elapsed_accounting_for_freeze(self.liberation_time)
        return result

    def nightfall_combo(self, cancel_last_smash=False, acquire_timeout=7.0, cancel_with_dodge=True):
        start = time.time()
        if not self.is_nightfall_ready():
            while not self.is_nightfall_ready() or time.time() - start < 1.6:
                self.click()
                if time.time() - start > acquire_timeout or not self.in_liberation:
                    return
                if self.should_end_liberation(time_only=True) and self.click_liber2():
                    return
                self.check_combat()
                self.task.next_frame()
        self.continues_normal_attack(0.5)
        if cancel_last_smash:
            start = time.time()
            while self.is_nightfall_ready(threshold=0.035):
                if time.time() - start > 2.5:
                    break
                self.click()
                self.task.next_frame()
            self.sleep(0.25, check_combat=False)
            if cancel_with_dodge:
                self.continues_right_click(0.1)
        else:
            self.nightfall_time = time.time()

    def is_nightfall_ready(self, threshold=0.15):
        box = self.task.box_of_screen_scaled(2560, 1440, 1853, 1233, 1964, 1344, name='zani_attack', hcenter=True)
        self.task.draw_boxes(box.name, box)
        light_percent = self.calculate_color_percentage_in_masked(zani_light_color, box, 0.425, 0.490)
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
        if result <= 0:
            self.nightfall_time = -1
            return 0
        return result

    def standard_defense_protocol_combo(self):
        if self.is_e_forte_full():
            return State.FORTE_FULL
        if self.resonance_available():
            self.click_resonance(send_click=False)
            self.sleep(0.2)
            # 普通 E 后普攻直到强化 E 图标亮（E 被怪规避时 forte 不涨——普攻充能抢出）；5s 有界防卡死
            end = time.time() + 5.0
            while not self.is_e_forte_full() and time.time() < end:
                self.task.click()
                self.sleep(0.1)
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
                # 蓄力重击改轻击连点（按住被误认强化E且命中时间拉长）
                self.continues_normal_attack(0.6)
                wait_chair = 1.15
                if (result := self.wait_forte_full(0.85, send_click=True)) != State.DONE:
                    return result
            elif result == State.FORTE_FULL:
                return State.FORTE_FULL
        else:
            wait_chair -= time.time() - self.chair_time
            self.chair_time = -1
        if (result := self.wait_forte_full(wait_chair)) != State.DONE:
            return result
        self.continues_normal_attack(0.2)
        return result

    def crisis_response_protocol_combo(self):
        self.check_combat()
        # 蓄力：一轮「E+普攻」涨一半，两轮满；找图失败与条不满无法区分——循环兜底不阻断
        if not self.is_e_forte_full():
            for _ in range(2):
                if self.is_e_forte_full():
                    break
                result = self.basic_attack_breakthrough()
                if result == State.FORTE_FULL:
                    break
        # 等强化E出现（普攻后时间差）再点击；找图失败 2s 超时兜底（blazes 增量把关）
        self.wait_until(self.is_e_forte_full, time_out=2, settle_time=0.15)
        self.send_resonance_key()
        self.crisis_time = time.time()
        return True

    def wait_forte_full(self, timeout=1, send_click=False) -> State:
        if timeout <= 0:
            return State.DONE
        kwargs = {'condition': self.is_e_forte_full, 'condition2': self.flying, 'time_out': timeout}
        if send_click:
            kwargs['post_action'] = self.click_with_interval
        result = self.wait_until(**kwargs)
        if result != State.INTERRUPTED:
            result = State.FORTE_FULL if result else State.DONE
        return result

    def wait_until(self, condition: Callable, condition2: Callable=lambda : None,
                   post_action: Callable=lambda : None, time_out: float=0, settle_time: float=0):
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
        from src.char.HavocRover import HavocRover
        if (char := self.task.has_char(Phoebe)):
            self.char_phoebe = char
            self.blazes_threshold = 0.6
        else:
            self.blazes_threshold = 0.4
        self.char_rover = self.task.has_char(HavocRover)
        self._zanfei_guang = bool(self.char_phoebe and self.char_rover)
        # 赞菲光下光主参与默认切人 buff 池（工厂全形态仍是 MainDps，不改 CharFactory）
        if self._zanfei_guang and self.char_rover is not None:
            self.char_rover.set_char_type(CharType.SUB_DPS)
            # 工厂显式喂过 buff_time=0（_buff_time_configured=True），set_char_type 不会重算，此处强制 14
            self.char_rover.set_buff_time(14)
            self.logger.info(
                f'zanfei: Rover local SubDps for switch char_type={self.char_rover.char_type} '
                f'buff_time={self.char_rover.buff_time}'
            )
        self.logger.info(f'zani decide_teammate zanfei={self._zanfei_guang} threshold={self.blazes_threshold}')

    def update_blazes(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 1627, 2014, 2176, 2017, name='zani_blazes', hcenter=True)
        blazes_percent = self.task.calculate_color_percentage(zani_blazes_color, box)
        blazes_percent = Decimal(str(blazes_percent)).quantize(Decimal('0.01'), rounding=ROUND_UP)
        self.blazes = blazes_percent

    def is_prepared(self):
        if self.is_current_char:
            self.update_blazes()
        if self.blazes >= self.blazes_threshold:
            return True
        if self.char_phoebe is not None and self.char_phoebe.state['outro'] >= 1 and (self.blazes >= 0.4):
            return True
        return False

    def wait_resonance_not_gray(self, send_click=False, liber_time_check=False, timeout=2.5):
        kwargs = {'condition': lambda : self.current_resonance() != 0, 'time_out': timeout, 'settle_time': 0.1}
        if send_click:
            kwargs['post_action'] = self.click_with_interval
        if liber_time_check:
            kwargs['condition2'] = lambda : self.liberation_time_left() < 1.0
        self.wait_until(**kwargs)

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if self._force_switch_me:
            # MUST+1：force 语义=必须切，避免与无条件 MUST（如开场 40s 未切过的角色）平级被 _oldest 截胡
            return SwitchPriority.MUST + 1
        for char in self.task.chars:
            if char is not None and char is not self and getattr(char, '_force_switch_me', False):
                return SwitchPriority.NO
        if self.in_liberation:
            return SwitchPriority.MUST
        if not self._zanfei_guang and has_intro:
            from src.char.Phoebe import Phoebe
            if not isinstance(current_char, Phoebe):
                self.logger.info(f'zani: reject intro source current={type(current_char).__name__} expected=Phoebe')
                return SwitchPriority.NO
        if has_intro and self.crisis_time_left() > 0:
            return SwitchPriority.NO
        return super().get_switch_priority(current_char, has_intro, target_low_con)

    def wait_switch(self):
        if self.has_intro and self.nightfall_time_left() > 0:
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
