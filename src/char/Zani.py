import time
from decimal import Decimal, ROUND_UP
from enum import Enum
from typing import Callable
import cv2
import numpy as np
import math
from src.char.BaseChar import BaseChar, CharType, SwitchPriority, forte_white_color
from ok import color_range_to_bound

class State(Enum):
    FORTE_FULL = 1
    DONE = 3
    FAILED = 4
    INTERRUPTED = 5

class Zani(BaseChar):

    def _reset_zani_state(self):
        """重置扩展状态。"""
        self.char_phoebe = None
        self.char_rover = None
        self._rover_form_pending = False
        self._no_target_streak = 0
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
        self._reset_zani_state()

    def reset_state(self):
        # 跨战斗清除大招状态。
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
        # 赞菲奶满协奏时切菲比，其余由框架选人。
        if (
            not self._zanfei_guang
            and self.is_con_full()
            and self.char_phoebe is not None
        ):
            return self._force_switch_to(self.char_phoebe)
        return super().switch_next_char(*args, **kwargs)

    def f_break(self, check_f_on_switch=False, force=False):
        # 保留框架签名，参数无需使用。
        """不执行处决，避免打断强化 E 与夜闪。"""
        return False

    def do_perform(self):
        if self.blazes_threshold == -1 or self._rover_form_pending:
            self.decide_teammate()
        # 非大招连续三轮无目标时退出战斗。
        if not self.in_liberation and not self.task.has_target():
            self._no_target_streak += 1
            if self._no_target_streak >= 3:
                self._no_target_streak = 0
                self.logger.info('zanfei: no target 3 rounds, exit combat')
                self.task.raise_not_in_combat('zanfei no target 3 rounds')
            return
        self._no_target_streak = 0
        if self._zanfei_guang:
            return self._do_perform_zanfei()
        entry_start = time.time()
        if not self.task.has_lavitator and self.has_intro:
            elapsed = time.time() - self.last_switch_in_time if self.last_switch_in_time > 0 else 0
            remaining = self.intro_motion_freeze_duration - elapsed
            if remaining > 0:
                self.continues_normal_attack(remaining)
            actual_elapsed = time.time() - self.last_switch_in_time if self.last_switch_in_time > 0 else -1
            self.logger.info(
                f'zani: intro-budget path=regular valid={self.last_switch_in_time > 0} '
                f'before={elapsed:.2f} applied={max(remaining, 0):.2f} after={actual_elapsed:.2f}'
            )
        else:
            self.wait_down()
        self.logger.info(f'zani: entry ready path=regular elapsed={time.time() - entry_start:.2f}')
        self.check_liber()
        if self.in_liberation:
            self.state = 1
            return self._do_liber_team2()
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
        self.logger.info(
            f'zani: trace non-liber sample forte={forte_full} e={e_available} '
            f'liber={liber_avail} blazes={self.blazes:.2f} intro={self.has_intro}'
        )
        if self.has_intro and self.blazes >= 1 and not liber_avail:
            self.sleep(0.2, check_combat=False)
            liber_avail = self.liberation_available()
            e_available = self.current_resonance() > 0.05
        # 强化 E 预计增加 0.1 焰光。
        return forte_full, e_available, liber_avail, float(self.blazes) + 0.1

    def _do_perform_zanfei(self):
        entry_start = time.time()
        if not self.task.has_lavitator and self.has_intro:
            elapsed = time.time() - self.last_switch_in_time if self.last_switch_in_time > 0 else 0
            remaining = self.intro_motion_freeze_duration - elapsed
            if remaining > 0:
                self.continues_normal_attack(remaining)
            actual_elapsed = time.time() - self.last_switch_in_time if self.last_switch_in_time > 0 else -1
            self.logger.info(
                f'zani: intro-budget path=zanfei valid={self.last_switch_in_time > 0} '
                f'before={elapsed:.2f} applied={max(remaining, 0):.2f} after={actual_elapsed:.2f}'
            )
        else:
            self.wait_down()
        self.logger.info(f'zani: entry ready path=zanfei elapsed={time.time() - entry_start:.2f}')
        self.check_liber()
        if self.in_liberation:
            self.state = 1
            return self._do_liber_zanfei()
        return self._non_liber_rotation(zanfei=True, reset_liber_phase=True)

    def _non_liber_rotation(self, zanfei=False, reset_liber_phase=False):
        """处理非大招轮转。

        赞菲光完成危机动作后直接尝试开大，赞菲奶按焰光阈值开大。
        """
        forte_full, e_available, liber_avail, predicted = self._sample_non_liber_rotation(
            reset_liber_phase=reset_liber_phase
        )

        self.logger.info(
            f'Zani._non_liber_rotation: start forte={forte_full} e={e_available} liber={liber_avail} '
            f'predicted={predicted:.2f} zanfei={zanfei}'
        )
        # 场景 3：可开大时直接尝试，失败则进入危机流程。
        if (zanfei or self.blazes >= 1) and liber_avail:
            self.logger.info('zani: trace non-liber branch=direct-liberation')
            success = self._try_liberation(zanfei=zanfei)
            if not success:
                self.sleep(0.1)
                success = self._try_liberation(zanfei=zanfei)
            if zanfei:
                return
            if success:
                # 开大成功后推进到第二阶段，再默认切人。
                self._liber_phase = 2
            return self.switch_next_char()
        if zanfei:
            # 赞菲光未就绪时，危机流程后直接尝试开大。
            if forte_full or e_available:
                self.logger.info('zani: trace non-liber branch=zanfei-crisis')
                self.crisis_response_protocol_combo()
                self._try_liberation(wait_crisis=True, zanfei=True)
                return
            # E 冷却时普攻后切人。
            self.normal_attack_until_can_switch()
            self.logger.info('zani: trace non-liber branch=zanfei-normal-attack')
            return self.switch_next_char()
        # 场景 4：强化 E 就绪时，预测焰光达标则开大。
        if forte_full:
            should_liberate = predicted >= self.blazes_threshold
            self.crisis_response_protocol_combo()
            # 仅在大招图标确认可用时开大。
            if should_liberate and self.liberation_available():
                if self._try_liberation(wait_crisis=True):
                    self._liber_phase = 2  # 同场景3：当轮 switch 即 phase1 切人
            return self.switch_next_char()
        # 场景 1：普通 E 可用时，危机充能后按阈值开大。
        if e_available:
            self.crisis_response_protocol_combo()
            if self.blazes >= self.blazes_threshold:
                # 图标识别失败时允许重试开大。
                if self.liberation_available() is not False:
                    if self._try_liberation(wait_crisis=True):
                        self._liber_phase = 2  # 同场景3：当轮 switch 即 phase1 切人
            return self.switch_next_char()
        # 场景 2：E 冷却时普攻直到可切人。
        self.normal_attack_until_can_switch()
        return self.switch_next_char()

    def _handoff_liber_insert(self, next_phase):
        """第一、二阶段默认切人，由落地角色执行插入轴。"""
        self._liber_phase = next_phase
        self._liber_handoff_token += 1
        self.logger.info(f'zanfei: liber insert handoff phase={next_phase} token={self._liber_handoff_token} default switch')
        return self.switch_next_char()

    def consume_liber_handoff(self):
        """仅消费一次插入交接令牌。"""
        if self._liber_handoff_token <= 0:
            return False
        self._liber_handoff_token = 0
        return True

    def try_consume_insert_handoff(self):
        """仅在大招第二、三阶段消费插入交接令牌。"""
        if not self.in_liberation or self._liber_phase not in (2, 3):
            return False
        return self.consume_liber_handoff()

    def _complete_liberation_to_phoebe(self, phase=0):
        self.logger.info(f'zani: trace r2-complete begin phase={phase} blazes={self.blazes}')
        self.logger.info('zani: trace r2-complete action=liber2 begin')
        if not self.click_liber2():
            self.logger.info('zani: trace r2-complete result=unconfirmed fallback=base-switch')
            return self.switch_next_char()
        self.logger.info(f'zani: trace r2-complete action=liber2 end state={self.state} in_liber={self.in_liberation}')
        self._liber_phase = phase
        self.logger.info(f'zani: trace r2-complete action=force-phoebe phase={phase}')
        return self._switch_to_phoebe_full()

    def _run_phase_three_liberation(self):
        if self.should_end_liberation():
            return self._complete_liberation_to_phoebe()
        self.nightfall_combo()
        if self._zanfei_guang:
            self.check_liber()
            if not self.in_liberation:
                self._liber_phase = 0
                return self._switch_to_phoebe_full()
            if self.should_end_liberation(force_finish=True):
                return self._complete_liberation_to_phoebe()
            self._liber_phase = 0
            return self.switch_next_char()
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
        """处理赞菲光大招阶段。"""
        if self._liber_phase == 2:
            self.logger.info('zanfei liber phase2: nightfall then default insert handoff')
            if self.should_end_liberation():
                return self._complete_liberation_to_phoebe()
            self.nightfall_combo()
            return self._handoff_liber_insert(3)
        if self._liber_phase == 3:
            self.logger.info('zanfei liber phase3: stay until R2')
            # 第三阶段打一段夜闪后收尾。
            return self._run_phase_three_liberation()
        if self.should_end_liberation():
            return self._complete_liberation_to_phoebe(phase=0)
        self.nightfall_combo()
        return self.switch_next_char()

    def _do_liber_team2(self):
        """处理赞菲奶大招阶段。"""
        if self._liber_phase == 2:
            self.logger.info('zanfei liber phase2: nightfall then switch')
            if self.should_end_liberation():
                return self._complete_liberation_to_phoebe()
            # 夜闪已在循环内完成 R2 时直接收尾。
            if self.nightfall_combo():
                return self._switch_to_phoebe_full()
            self._liber_phase = 3
            return self.switch_next_char()
        if self._liber_phase == 3:
            self.logger.info('zanfei liber phase3: stay until R2')
            return self._run_phase_three_liberation()
        # 阶段异常时按第一阶段流程恢复。
        self.logger.info('zanfei liber phase1: nightfall then switch')
        if self.should_end_liberation():
            return self._complete_liberation_to_phoebe(phase=0)
        if self.nightfall_combo():
            return self._switch_to_phoebe_full()
        self._liber_phase = 2
        return self.switch_next_char()

    def _switch_to_phoebe_full(self):
        phoebe = self.char_phoebe
        if phoebe is None:
            from src.char.Phoebe import Phoebe
            phoebe = self.task.has_char(Phoebe)
            self.char_phoebe = phoebe
        if phoebe is None:
            self.logger.info('zani: trace r2-switch result=no-phoebe fallback=base-switch')
            return self.switch_next_char()
        self.logger.info(
            f'zani: force switch to Phoebe (full perform after R2) '
            f'trace=begin phoebe_att={phoebe.attribute} star={phoebe.star_available} '
            f'charges={phoebe.remaining_charges}'
        )
        self.logger.info('zani: trace r2-switch action=phoebe-reset-action')
        phoebe.reset_action()
        self._liber_handoff_token = 0
        self._liber_phase = 0
        self.logger.info('zani: trace r2-switch input=force-switch-phoebe')
        return self._force_switch_to(phoebe)

    def _try_liberation(self, wait_crisis=False, zanfei=False):
        if wait_crisis:
            before_blazes = self.blazes
            self.wait_crisis_protocol_end()
            if zanfei:
                self.update_blazes()
            # 危机动作后确认焰光增加，再尝试开大。
            if not self._wait_enhanced_e_commit(before_blazes):
                return False
        if self.echo_available():
            self.click_echo(time_out=0)
        if self.click_liberation(send_click=True):
            self._liberation_followup(zanfei=zanfei)
            return True
        return False

    def _wait_enhanced_e_commit(self, before_blazes):
        elapsed_now = lambda: self.time_elapsed_accounting_for_freeze(
            self.crisis_time, intro_motion_freeze=True
        )
        # 每次判断重新计算危机动作已过时间。
        elapsed = elapsed_now() if self.crisis_time > 0 else -1
        if 0 <= elapsed < 2.0:
            self.wait_until(lambda: elapsed_now() >= 2.0, time_out=3.0)
            elapsed = elapsed_now()
        # 强化 E 结算后轮询焰光，最多等待至 4.5 秒。
        while self.blazes <= before_blazes and elapsed >= 2.0 and elapsed < 4.5:
            self.sleep(0.4)
            self.update_blazes()
            elapsed = elapsed_now()
        # 焰光未增加视为强化 E 未命中。
        committed = elapsed >= 2.0 and self.blazes > before_blazes
        self.logger.info(f'zani: enhanced E commit elapsed={elapsed:.2f}s blazes={before_blazes}->{self.blazes} committed={committed}')
        return committed

    def _start_liberation(self):
        self._liber_handoff_token = 0
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

    def click_liber2(self):
        start = time.time()
        total_deadline = start + 6.0
        cast_started_at = None
        self.logger.info('zani: trace liber2 begin')
        self.task.in_liberation = True
        send_key = True
        not_liber_box = self.task.box_of_screen_scaled(2560, 1440, 1909, 1274, 1957, 1322, name='zani_not_liber_box', hcenter=True)
        inputs = 0
        while True:
            now = time.time()
            if now >= total_deadline:
                self.task.in_liberation = False
                # 超时后先清除状态，再按当前画面确认。
                self.in_liberation = False
                if not self.check_liber():
                    self.update_blazes()
                self.logger.info(f'zani: trace liber2 end reason=timeout inputs={inputs}')
                return False
            if self.task.find_one('box_target_enemy_inner', box=not_liber_box, threshold=0.75):
                break
            if self.current_resonance() == 0:
                send_key = True
            elif cast_started_at is not None and now - cast_started_at > 1.5:
                send_key = False
            if send_key:
                if inputs == 0:
                    self.logger.info('zani: trace liber2 input=liber-key')
                self.send_liberation_key()
                if cast_started_at is None:
                    cast_started_at = now
                inputs += 1
            self.task.next_frame()
        self.task.in_liberation = False
        current = time.time()
        duration = 2.25
        confirmed = cast_started_at is not None and current - cast_started_at >= duration
        if confirmed:
            self.add_freeze_duration(current - duration, duration, 0)
            self.logger.info('clicked liber2')
        else:
            self.logger.info(f'zani: liber2 target detected before confirmation duration={current - start:.2f}s')
        self.in_liberation = False
        self.blazes = -1
        self.liberation_time = -1
        self.state = 0
        self.logger.info(f'zani: trace liber2 end reason=target-detected total={current - start:.2f}s cast={current - cast_started_at if cast_started_at is not None else 0:.2f}s inputs={inputs} confirmed={confirmed}')
        return confirmed

    def should_end_liberation(self, time_only=False, force_finish=False):
        start = time.time()
        left = self.liberation_time_left()
        mode = 'time-only' if time_only else 'full'
        smash_left = 0.0
        raw_elapsed = -1.0
        if not time_only and self._liber_phase == 3 and self.nightfall_time > 0:
            raw_elapsed = time.time() - self.nightfall_time
            if raw_elapsed < 2.2 + 3.0:
                smash_left = self.nightfall_time_left()

        # 强制收尾时先等待已触发的下砸落地。
        if force_finish:
            if smash_left > 0.12:
                wait = smash_left - 0.12
                self.logger.info(
                    f'zani: r2-gate smash-guard phase={self._liber_phase} '
                    f'smash_left={smash_left:.2f} raw_elapsed={raw_elapsed:.2f} '
                    f'wait={wait:.2f} forced=True left_before={left:.2f}'
                )
                self.sleep(wait, check_combat=False)
                self.check_liber()
                if not self.in_liberation:
                    return False
            self.logger.info(
                f'zani: r2-gate result=end reason=forced-smash-cleared '
                f'phase={self._liber_phase} smash_left={smash_left:.2f} '
                f'left={left:.2f} elapsed={time.time() - start:.2f}'
            )
            return True

        if left < 1.0:
            self.logger.info(
                f'zani: r2-gate result=end reason=time-left mode={mode} '
                f'left={left:.2f} elapsed={time.time() - start:.2f}'
            )
            self.logger.info('Liberation is about to end, perform liberation2')
            return True
        if time_only:
            return False

        # 赞菲光由外层完成首段夜闪后收尾。
        if self._zanfei_guang and self._liber_phase == 3:
            if smash_left > 0.12:
                wait = smash_left - 0.12
                self.logger.info(
                    f'zani: r2-gate smash-guard phase={self._liber_phase} '
                    f'smash_left={smash_left:.2f} raw_elapsed={raw_elapsed:.2f} '
                    f'wait={wait:.2f} forced=False left_before={left:.2f}'
                )
                self.sleep(wait, check_combat=False)
                self.check_liber()
                if not self.in_liberation:
                    return False
                self.logger.info(
                    f'zani: r2-gate result=continue reason=smash-settled '
                    f'phase={self._liber_phase} smash_left={smash_left:.2f} '
                    f'left={left:.2f} elapsed={time.time() - start:.2f}'
                )
            return False

        if self.is_nightfall_ready():
            self.logger.info(
                f'zani: r2-gate result=continue reason=nightfall-ready left={left:.2f} '
                f'elapsed={time.time() - start:.2f}'
            )
            return False
        if not self.is_mouse_forte_full():
            # 仅第三阶段可按下砸状态结束大招，前两阶段继续切人流程。
            if self._liber_phase != 3:
                self.logger.info(
                    f'zani: r2-gate result=continue reason=phase-early '
                    f'phase={self._liber_phase} left={left:.2f} '
                    f'elapsed={time.time() - start:.2f}'
                )
                return False
            # 赞菲奶固定等待下砸落地后再释放 R2。
            if smash_left > 0.12:
                wait = 1.4
                self.logger.info(
                    f'zani: r2-gate smash-guard phase={self._liber_phase} '
                    f'smash_left={smash_left:.2f} '
                    f'raw_elapsed={raw_elapsed:.2f} wait={wait:.2f} '
                    f'left_before={left:.2f}'
                )
                self.sleep(wait, check_combat=False)
                self.check_liber()
                if not self.in_liberation:
                    return False
            self.logger.info(
                f'zani: r2-gate result=end reason=smash-cleared phase={self._liber_phase} '
                f'smash_left={smash_left:.2f} left={left:.2f} elapsed={time.time() - start:.2f}'
            )
            self.logger.info('Cannot perform another nightfall, perform liberation2')
            return True
        self.logger.info(
            f'zani: r2-gate result=continue reason=forte-ready left={left:.2f} '
            f'elapsed={time.time() - start:.2f}'
        )
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
                if self.should_end_liberation(time_only=True):
                    return self.click_liber2()
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
            # 普通 E 后普攻至强化 E 就绪，最多 5 秒。
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
                # 蓄力重击失败时改用普攻。
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
        initial_forte = self.is_e_forte_full()
        self.logger.info(f'zani: trace crisis begin forte={initial_forte}')
        # 最多执行两轮危机充能。
        if not initial_forte:
            for attempt in range(2):
                if self.is_e_forte_full():
                    self.logger.info(f'zani: trace crisis forte-ready attempt={attempt}')
                    break
                result = self.basic_attack_breakthrough()
                self.logger.info(f'zani: trace crisis breakthrough attempt={attempt + 1} result={result}')
                if result == State.FORTE_FULL:
                    break
        # 最多等待 2 秒确认强化 E 图标。
        ready = self.wait_until(self.is_e_forte_full, time_out=2, settle_time=0.15)
        self.logger.info(f'zani: trace crisis wait-forte ready={ready} current={self.is_e_forte_full()}')
        self.logger.info('zani: trace crisis input=resonance-E')
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

    def wait_until(self, condition: Callable, condition2: Callable=None,
                   post_action: Callable=None, time_out: float=0, settle_time: float=0):
        """等待条件成立、中断条件触发或超时。

        条件成立返回 True，超时返回 False，中断返回 State.INTERRUPTED。
        """
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
            if condition2 is not None and condition2():
                return State.INTERRUPTED
            # 每次等待只检查一次战斗状态。
            if once:
                self.check_combat()
                once = False
            if post_action is not None:
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
        from src.char.Rover import Rover
        if (char := self.task.has_char(Phoebe)):
            self.char_phoebe = char
            self.blazes_threshold = 0.6
        else:
            self.blazes_threshold = 0.4
        self.char_rover = self.task.has_char(Rover)
        rover_form = (
            self.task.get_known_ring_index(self.char_rover)
            if self.char_rover is not None and hasattr(self.task, 'get_known_ring_index')
            else getattr(self.char_rover, 'ring_index', -1)
        )
        self._rover_form_pending = self.char_rover is not None and rover_form < 0
        self._zanfei_guang = bool(self.char_phoebe and self.char_rover)
        if self._zanfei_guang and self.char_rover is not None:
            self.char_rover.set_char_type(CharType.SUB_DPS)
            self.char_rover.set_buff_time(14)
            self.logger.info(
                f'zanfei: Rover local SubDps for switch char_type={self.char_rover.char_type} '
                f'buff_time={self.char_rover.buff_time}'
            )
        self.logger.info(
            f'zani decide_teammate zanfei={self._zanfei_guang} threshold={self.blazes_threshold} '
            f'rover_form={rover_form} pending={self._rover_form_pending}'
        )

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
            return SwitchPriority.MUST + 1
        for char in self.task.chars:
            if char is not None and char is not self and getattr(char, '_force_switch_me', False):
                return SwitchPriority.NO
        if self.in_liberation:
            return SwitchPriority.MUST
        if not self._zanfei_guang and self.char_phoebe is not None and has_intro:
            from src.char.Phoebe import Phoebe
            if not isinstance(current_char, Phoebe):
                self.logger.info(f'zani: reject intro source current={type(current_char).__name__} expected=Phoebe')
                return SwitchPriority.NO
        if has_intro and self.crisis_time_left() > 0:
            return SwitchPriority.NO
        return super().get_switch_priority(current_char, has_intro, target_low_con)

    def wait_switch(self):
        if self.has_intro:
            nightfall_left = self.nightfall_time_left()
            if nightfall_left > 0 and self.liberation_time_left() >= 2:
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
