import time
import cv2
import numpy as np
from enum import Enum
from src.char.BaseChar import BaseChar, CharType, SwitchPriority, forte_white_color
from ok import color_range_to_bound

class State(Enum):
    SUCCESS = 1
    UNAVAILABLE = 2
    TIMEOUT = 3

class Phoebe(BaseChar):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attribute = 0
        self.star_available = False
        self.char_zani = None
        self.char_rover = None
        self.attribute_mismatch = False
        self.first_rotation_done = False
        self._zanfei_guang = False
        self._force_switch_me = False
        self.state = {'enter_status': 0, 'starflash_combo': 0, 'liberation': 0, 'outro': 0, 'priority_liberation_cast': 0}

    def reset_state(self):
        super().reset_state()
        self.attribute = 0
        self.star_available = False
        self.char_zani = None
        self.char_rover = None
        self.first_rotation_done = False
        self._zanfei_guang = False
        self._force_switch_me = False
        # 跨战斗必须清掉抢大招成功标记，避免 pre-switch 误判 duplicate
        self.state = {'enter_status': 0, 'starflash_combo': 0, 'liberation': 0, 'outro': 0, 'priority_liberation_cast': 0}

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if self._force_switch_me:
            return SwitchPriority.MUST
        for char in self.task.chars:
            if char is not None and char is not self and getattr(char, '_force_switch_me', False):
                return SwitchPriority.NO
        if not has_intro and self.last_outro_time > 0 and (self.time_elapsed_accounting_for_freeze(self.last_outro_time, intro_motion_freeze=True) < 4.5):
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

    def _in_zani_liber_insert_window(self):
        """赞妮大招 phase1/2 默认切人后：phase 2/3 落地即跑 insert 短轴（含切到菲比）。"""
        if not self._zanfei_guang:
            return False
        if self.attribute == 0:
            self.decide_teammate()
        zani = self.char_zani
        if zani is None:
            from src.char.Zani import Zani
            zani = self.task.has_char(Zani)
            self.char_zani = zani
        if zani is None:
            return False
        return bool(zani.try_consume_insert_handoff())

    def do_perform(self):
        if self._zanfei_guang and self._in_zani_liber_insert_window():
            return self._do_liber_insert()
        return self._do_regular_rotation()

    def _prepare_regular_rotation(self):
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
        return start

    def _resolve_linkage_or_exit(self):
        if self.flying():
            self.continues_normal_attack(0.1)
            return True, self.switch_next_char(), False
        attribute_mismatch = self.check_attribute_mismatch()
        if self.attribute == 2 and self.char_zani is not None:
            if not self.star_available:
                self.absolution_or_confession()
            if self.zani_linkage():
                return True, self.switch_next_char(), attribute_mismatch
        return False, None, attribute_mismatch

    def _run_starflash_budget(self, status_entered):
        zanfei_support_fallback = bool(
            self._zanfei_guang and self.attribute == 2 and self.star_available
        )
        if not (
            status_entered == State.SUCCESS
            or self.judge_forte() > 0
            or (self.star_available and self.is_forte_full())
            or (self.star_available and self.state.get('priority_liberation_cast'))
            or zanfei_support_fallback
        ):
            return
        if zanfei_support_fallback and status_entered != State.SUCCESS and self.judge_forte() == 0 and not self.is_forte_full():
            self.logger.info('phoebe: zanfei support heavy fallback, forte/confession not registered yet')
        self.starflash_combo()
        self._try_liberation_now()
        max_starflash = 1 if self._zanfei_guang else 2
        if self.attribute == 2 and self.state['starflash_combo'] < max_starflash and self.get_zani_state() != 1:
            self.starflash_combo()

    def _finish_regular_rotation(self):
        if self.resonance_available():
            if self.attribute == 2:
                if not self._zanfei_guang and not self.confession_ready() and self.first_rotation_done:
                    self.click_resonance(send_click=False, time_out=0.5)
            else:
                self.click_resonance()
            self._ensure_first_rotation_con()
            return self.switch_next_char(_zanfei_full_tail=self._zanfei_guang)
        self.continues_normal_attack(0.1)
        self._ensure_first_rotation_con()
        self.switch_next_char(_zanfei_full_tail=self._zanfei_guang)

    def _do_regular_rotation(self):
        start = self._prepare_regular_rotation()
        exited, result, attribute_mismatch = self._resolve_linkage_or_exit()
        if exited:
            return result
        wait_ui_time = 0.35 - (time.time() - start)
        if wait_ui_time > 0 and self.star_available and self.judge_forte() == 0:
            self.continues_normal_attack(wait_ui_time)
        status_entered = self.absolution_or_confession()
        self.check_combat()
        if (not attribute_mismatch or status_entered == State.SUCCESS) and self.star_available:
            if self._click_liberation_reliable(tag=' do-perform'):
                self._record_liberation_cast()
            elif (
                not self.state.get('priority_liberation_cast')
                and self.liberation_available()
                and not self.flying()
                and self._click_liberation_reliable(tag=' do-perform-retry')
            ):
                # R 已可用时只多点一次（UI 抖动）；不可用则绝不空等
                self._record_liberation_cast()
        self._run_starflash_budget(status_entered)
        self._try_liberation_now()
        return self._finish_regular_rotation()

    def _do_liber_insert(self):
        """赞妮大招插入：starflash + 长按定身E + 有大招则放，切回赞妮（禁止短按传送/闪避起飞）。"""
        self.logger.info('phoebe: zani liber insert short axis')
        if self.attribute == 0:
            self.decide_teammate()
        self._ensure_grounded('insert enter')
        self.sleep(0.5)
        if self.has_intro:
            self.continues_normal_attack(0.8)
            self._ensure_grounded('insert after intro na')
        if not self.star_available:
            self.absolution_or_confession(dodge_cancel=False)
            self._ensure_grounded('insert after confession')
        if self._try_liberation_now():
            self.logger.info('phoebe: liber insert cast liberation')
            self._ensure_grounded('insert after liber')
        starflash_recovered = False
        if self.judge_forte() > 0 or self.is_forte_full():
            starflash_recovered = self.starflash_combo()
            self._ensure_grounded('insert after heavy')
        if self._try_liberation_now():
            self.logger.info('phoebe: liber insert cast liberation after starflash')
            self._ensure_grounded('insert after liber2')
        if not starflash_recovered:
            self._insert_long_press_dingshen_e()
        self._ensure_grounded('insert before switch')
        if self.buff_time > 0:
            self.last_buff_time = time.time()
            self.logger.info(f'phoebe: insert buff refreshed buff_time={self.buff_time}')
        from src.char.Zani import Zani
        zani = self.char_zani or self.task.has_char(Zani)
        return super().switch_next_char()

    def _ensure_grounded(self, tag=''):
        """插入轴落地，避免重击/技能后滞空切人。"""
        self.wait_down()
        if self.flying():
            self.logger.info(f'phoebe: wait land {tag}')
            self.task.wait_until(lambda : not self.flying(), post_action=lambda : self.click(interval=0.1, after_sleep=0.05), time_out=2.0)
            self.wait_down()

    def _hold_resonance_key_055(self):
        key = self.get_resonance_key()
        self.task.send_key_down(key)
        hold_start = time.time()
        while time.time() - hold_start < 0.55:
            self.task.next_frame()
        self.task.send_key_up(key)
        self.sleep(0.05)

    def _insert_long_press_dingshen_e(self):
        """大招插入定身：E 可用则长按；绝不用短按二段传送。"""
        if not self.resonance_available():
            return False
        if self.confession_ready() or self.star_available:
            self.logger.info('phoebe: insert long-press E dingshen')
            self._hold_resonance_key_055()
            return True
        return False

    LIBER_HOLD_GRACE = 3.0
    LIBER_NO_EFFECT_HOLD = 2.0
    LIBER_RESOLVE_TIMEOUT = 3.5
    LIBER_SETTLE_TIMEOUT = 2.0
    LIBER_EXTENDED_CONFIRM = 1.0

    def _liber_pending(self):
        """liberation not cast yet this rotation (star ready but no cast recorded)."""
        return bool(self.star_available) and (not self.state.get('priority_liberation_cast'))

    def _record_liberation_cast(self):
        self.state['liberation'] += 1
        self.state['priority_liberation_cast'] = 1
        self.check_combat()

    def _mark_liber_no_effect(self):
        self.state['liber_no_effect_at'] = time.time()

    def _recent_liber_no_effect(self):
        ts = self.state.get('liber_no_effect_at') or 0
        return bool(ts) and (time.time() - ts < self.LIBER_NO_EFFECT_HOLD)

    def _confirm_liberation_transition(self, outcome, tag):
        if not self.task.wait_until(
            lambda: not self.task.in_team()[0],
            time_out=self.LIBER_EXTENDED_CONFIRM,
            post_action=self.click_with_interval,
        ):
            return False
        self.task.in_liberation = True
        self.state['liber_no_effect_at'] = 0
        self.logger.info(f'phoebe: liber cast confirmed {outcome}{tag}')
        return True

    def _click_liberation_reliable(self, send_click=True, tag=''):
        """Base no-effect is only a 0.4s animation miss - confirm longer and retry once."""
        if self.click_liberation(send_click=send_click):
            self.state['liber_no_effect_at'] = 0
            return True
        self.logger.info(f'phoebe: liber no-effect, extended confirm{tag}')
        if self._confirm_liberation_transition('after extended wait', tag):
            return True
        if self.liberation_available():
            self.logger.info(f'phoebe: liber retry after no-effect{tag}')
            if self.click_liberation(send_click=send_click):
                self.state['liber_no_effect_at'] = 0
                return True
            if self._confirm_liberation_transition('after retry', tag):
                return True
        self._mark_liber_no_effect()
        return False

    def _should_hold_for_liber(self, check_liber, con_full_since):
        """Hold past con-full while liber pending and still obtainable / recovering from no-effect."""
        if not (check_liber and self._liber_pending()):
            return False
        if con_full_since is not None and time.time() - con_full_since >= self.LIBER_HOLD_GRACE:
            return False
        if self.liberation_available():
            return True
        return self._recent_liber_no_effect()

    def _attack_until_con(self, timeout, check_liber=True, interval=0.1):
        end = time.time() + timeout
        con_full_since = None
        while time.time() < end:
            if self.is_con_full():
                if con_full_since is None:
                    con_full_since = time.time()
                if not self._should_hold_for_liber(check_liber, con_full_since):
                    break
            else:
                con_full_since = None
            if check_liber and self.star_available and (not self.flying()) and (
                self.liberation_available() or self._recent_liber_no_effect()
            ):
                if self.liberation_available() and self._try_liberation_now():
                    continue
            if time.time() >= end:
                break
            self.task.click()
            self.sleep(interval)

    def _ensure_first_rotation_con(self):
        """切人前补协奏：赞菲光每轮最多10秒；非赞菲光完整轴最多5秒。"""
        # 只要已在星状态，补协奏阶段都允许大招抢普攻（不限赞菲光）
        allow_liber = bool(self.star_available)
        if self._zanfei_guang:
            if (not self.is_con_full()) or self._liber_pending():
                self._attack_until_con(10.0, check_liber=allow_liber)
            self.first_rotation_done = True
            return
        if not self.first_rotation_done:
            self.first_rotation_done = True
        start_con = self.get_current_con()
        if start_con == 1 or self.get_zani_state() == 1:
            return
        self._attack_until_con(5.0, check_liber=allow_liber)

    def zani_linkage(self):
        result = self.get_zani_state()
        # 必须先处理赞妮大招中：blazes 常年 >=0.9，若先判 blazes 会永远跳过 cast_remaining_skills/starflash
        if result == 1:
            self.cast_remaining_skills()
            return True
        if self.char_zani.blazes >= 0.9:
            # 停光噪让场前，若 star/重击已就绪先补 starflash，避免第二轮只普攻
            if self.star_available and (self.judge_forte() > 0 or self.is_forte_full()):
                self.starflash_combo()
            if not self.resonance_available():
                if result == 0 or self.char_zani.liberation_time_left() > 3:
                    self.continues_normal_attack(1, interval=0.15)
            elif not self._zanfei_guang and self.first_rotation_done and (not self.confession_ready()):
                self.click_resonance(send_click=False)
            return True

    def check_attribute_mismatch(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 1890, 2010, 1915, 2030, name='phoebe_middle_star', hcenter=True)
        self.task.draw_boxes(box.name, box)
        star_light_percent = self.task.calculate_color_percentage(phoebe_star_light_color, box)
        star_blue_percent = self.task.calculate_color_percentage(phoebe_star_blue_color, box)
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
        for _ in range(skill_count):
            if liber and self.state['liberation'] < 1:
                if self.liberation_available() and self.click_liberation(send_click=False):
                    self.state['liberation'] += 1
            # 告解态 starflash 依赖重击就绪；仅 prayer 格 >0 会漏掉已可重击的情况
            if self.judge_forte() > 0 or self.is_forte_full():
                self.starflash_combo()
                self.task.next_frame()
                start = time.time()
        return start

    def judge_forte(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 1633, 2004, 2160, 2014, name='phoebe_forte1', hcenter=True)
        if self.attribute == 1:
            forte = self.calculate_forte_num(phoebe_forte_light_color, box, 4, 25)
        else:
            forte = self.calculate_forte_num(phoebe_forte_blue_color, box, 2, 50)
        return forte

    STARFLASH_RECOVER_AFTER = 2.0

    def _starflash_recover_with_e(self):
        """乱轴后主动长按 E + 后撑，把自己拉回 starflash 状态。"""
        if not self.resonance_available():
            self.logger.info('phoebe: starflash recover skip, E not ready')
            return False
        self.logger.info('phoebe: starflash recover long-press E + backstep')
        self._hold_resonance_key_055()
        self._ensure_grounded('starflash recover')
        self.continues_right_click(0.1)
        return True

    def starflash_combo(self):
        start = time.time()
        check_forte = start
        condition = self.get_prayer_condition()
        recover_used = False
        recover_tried = False
        if not condition() and not self.is_forte_full():
            while not self.is_forte_full():
                if self.flying():
                    self.shorekeeper_auto_dodge()
                self.click()
                if time.time() - start > 5:
                    return recover_used
                if (
                    not recover_tried
                    and self._zanfei_guang
                    and time.time() - start > self.STARFLASH_RECOVER_AFTER
                ):
                    recover_tried = True
                    if self._starflash_recover_with_e():
                        recover_used = True
                        check_forte = time.time()
                        self.task.next_frame()
                        continue
                if time.time() - check_forte > 1:
                    if condition() or self.judge_forte() == 0:
                        return recover_used
                else:
                    check_forte = time.time()
                self.check_combat()
                self.task.next_frame()
            self.continues_right_click(0.05)
        if self.star_available:
            if not self.confession_ready():
                # 星标字段在但蓝条未识别：实机可能已退出告解形态，重新进入（避免重复告解乱轴）
                self.absolution_or_confession(dodge_cancel=False)
            if self.is_forte_full():
                cast = False
                flying = False
                outer_start = time.time()
                while self.is_forte_full():
                    if time.time() - outer_start > 2:
                        break
                    self.task.mouse_down()
                    mouse_hold_start = time.time()
                    while time.time() - mouse_hold_start < 0.5:
                        if not self.is_forte_full():
                            cast = True
                            break
                        if flying := self.flying():
                            break
                        self.task.next_frame()
                    self.task.mouse_up()
                    if flying:
                        self._ensure_grounded('starflash heavy')
                        outer_start = time.time()
                    self.check_combat()
                    self.task.next_frame()
                else:
                    cast = True
                if cast:
                    self.state['starflash_combo'] += 1
        return recover_used

    def confession_ready(self):
        box = self.task.box_of_screen_scaled(2560, 1440, 2110, 1236, 2217, 1343, name='phoebe_resonance', hcenter=False)
        self.task.draw_boxes(box.name, box)
        from src.char.Zani import Zani
        blue_percent = Zani.calculate_color_percentage_in_masked(self, phoebe_blue_color, box, 0.425, 0.490)
        return blue_percent > 0.15

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
                    self.task.wait_until(lambda : not self.flying(),
                                         post_action=lambda : self.click(interval=0.1, after_sleep=0.1), time_out=2)
                    outer_start = time.time()
                self.task.next_frame()
            if self.attribute == 2:
                self.logger.info('Enters confession status')
            else:
                self.logger.info('Enters absolution status')
            if dodge_cancel:
                self.continues_right_click(0.05)
            self.star_available = True
            self.reset_action()
            self.state['enter_status'] += 1
            return State.SUCCESS
        return State.UNAVAILABLE

    def _try_liberation_now(self):
        """Try liberation immediately; True if cast succeeded."""
        if self.star_available and (not self.flying()) and self.liberation_available():
            if self._click_liberation_reliable(tag=' try-now'):
                self._record_liberation_cast()
                return True
        return False

    def _try_cast_liberation_before_switch(self):
        if (
            self.attribute != 2
            or self.state.get('priority_liberation_cast')
            or not self.star_available
            or self.flying()
            or not self.liberation_available()
        ):
            self.logger.info('phoebe: pre-switch liber diag=v5-pre-switch-r2 stage=soft outcome=not-ready')
            return False
        if self._click_liberation_reliable(tag=' soft'):
            self._record_liberation_cast()
            self.logger.info('phoebe: pre-switch liber diag=v5-pre-switch-r2 stage=soft outcome=cast-success')
            return True
        self.logger.info('phoebe: pre-switch liber diag=v5-pre-switch-r2 stage=soft outcome=cast-failed')
        return False

    def _resolve_pending_liberation(self, timeout, tag, max_attempts=None, stop_on_star_loss=False):
        start = time.time()
        attempts = 0
        result = 'already-success' if self.state.get('priority_liberation_cast') else 'availability-timeout'
        if result == 'already-success' or not self.star_available:
            return result == 'already-success', attempts, 'star-unavailable' if not self.star_available else result
        while time.time() - start < timeout:
            if stop_on_star_loss and (self.state.get('priority_liberation_cast') or not self.star_available):
                result = 'already-success' if self.state.get('priority_liberation_cast') else 'star-unavailable'
                return result == 'already-success', attempts, result
            if self.flying():
                result = 'airborne-timeout'
                self.click(interval=0.1)
                self.task.next_frame()
                continue
            result = 'availability-timeout'
            available = self.liberation_available()
            if available:
                attempts += 1
                if self._click_liberation_reliable(tag=tag):
                    self._record_liberation_cast()
                    return True, attempts, 'cast-success'
                if max_attempts is not None and attempts >= max_attempts:
                    return False, attempts, 'cast-failed-limit'
            self.click(interval=0.05)
            self.task.next_frame()
        return False, attempts, result

    def _settle_zanfei_liberation_before_switch(self):
        start = time.time()
        settled, attempts, result = self._resolve_pending_liberation(
            self.LIBER_SETTLE_TIMEOUT, ' settle', max_attempts=3
        )
        elapsed = min(time.time() - start, self.LIBER_SETTLE_TIMEOUT)
        self.logger.info(
            f'phoebe: pre-switch liber diag=v5-pre-switch-r2 stage=settlement '
            f'result={result} elapsed={elapsed:.2f}s attempts={attempts}'
        )
        return settled

    def _block_switch_until_liber_resolved(self):
        """Settlement failed while pending: bounded retry before full-con outro to Zani."""
        self.logger.info(
            f'phoebe: block switch until liber resolved pending={self._liber_pending()} '
            f'avail={self.liberation_available()} timeout={self.LIBER_RESOLVE_TIMEOUT}'
        )
        resolved, _, result = self._resolve_pending_liberation(
            self.LIBER_RESOLVE_TIMEOUT, ' block-switch', stop_on_star_loss=True
        )
        if resolved or result == 'star-unavailable':
            if result == 'cast-success':
                self.logger.info('phoebe: liber resolved before switch')
            return True
        self.logger.info(
            f'phoebe: liber resolve timeout, allow switch pending={self._liber_pending()} '
            f'avail={self.liberation_available()}'
        )
        return False

    def _prepare_exit(self, full_tail):
        self._try_cast_liberation_before_switch()
        if not (self.attribute == 2 and self.is_con_full() and full_tail and self._zanfei_guang):
            return
        if (not self._settle_zanfei_liberation_before_switch()) and self._liber_pending() and self.star_available:
            self._block_switch_until_liber_resolved()

    def switch_next_char(self, *args, **kwargs):
        full_tail = bool(kwargs.pop('_zanfei_full_tail', False))
        self._prepare_exit(full_tail)
        if self.attribute == 2 and self.is_con_full():
            self.click_echo()
            self.state['outro'] += 1
            if self._zanfei_guang:
                return self._zanfei_switch_on_full_con()
        return super().switch_next_char(*args, **kwargs)

    def _zanfei_switch_on_full_con(self):
        from src.char.Zani import Zani
        target = self.char_zani or self.task.has_char(Zani)
        self.logger.info('phoebe: zanfei full-con outro -> Zani')
        return self._force_switch_to(target)

    def check_middle_star(self):
        if self.star_available:
            return True
        box = self.task.box_of_screen_scaled(3840, 2160, 1890, 2010, 1915, 2030, name='phoebe_middle_star', hcenter=True)
        if self.attribute == 1:
            forte_percent = self.task.calculate_color_percentage(phoebe_star_light_color, box)
            if forte_percent > 0.25:
                self.star_available = True
                return True
        elif self.attribute == 2:
            forte_percent = self.task.calculate_color_percentage(phoebe_star_blue_color, box)
            if forte_percent > 0.25:
                self.star_available = True
                return True
        return False

    def decide_teammate(self):
        from src.char.Zani import Zani
        from src.char.Cartethyia import Cartethyia
        from src.char.HavocRover import HavocRover
        self.char_rover = self.task.has_char(HavocRover)
        if (char := self.task.has_char(Zani)):
            self.char_zani = char
            self.attribute = 2
            self._zanfei_guang = bool(self.char_rover)
        elif self.task.has_char(Cartethyia) and self.char_rover:
            self.attribute = 2
            self._zanfei_guang = False
        else:
            self.attribute = 1
            self._zanfei_guang = False
        # 与 Zani.decide_teammate 一致：赞菲光下光主局部 SubDps，便于默认切人进 buff 池
        if self._zanfei_guang and self.char_rover is not None:
            self.char_rover.set_char_type(CharType.SUB_DPS)
            # 同 Zani：工厂 buff_time=0 已标记 configured，必须显式设 14 才能进 buff 池
            self.char_rover.set_buff_time(14)
            self.logger.info(
                f'phoebe: zanfei Rover local SubDps char_type={self.char_rover.char_type} '
                f'buff_time={self.char_rover.buff_time}'
            )

    def judge_amplitude(self, gray, min_amp):
        height, width = gray.shape[:]
        if height == 0 or width < 64 or not np.array_equal(np.unique(gray), [0, 255]):
            return False
        profile = np.sum(gray == 255, axis=0).astype(np.float32)
        profile -= np.mean(profile)
        return np.max(np.abs(np.fft.fft(profile))[1:]) >= min_amp

    def calculate_forte_num(self, forte_color, box, num=1, min_amp=50):
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
            score = self.judge_amplitude(gray, min_amp)
            if fail_count == 0:
                if score:
                    forte += 1
                else:
                    fail_count += 1
            elif score:
                warning = True
            else:
                fail_count += 1
            left += step
        if warning:
            self.logger.debug('Frequncy analysis error, return the forte before mistake.')
        return forte

    def get_zani_state(self):
        if self.attribute == 2 and self.char_zani is not None:
            return self.char_zani.get_state()

    def reset_action(self):
        if self.attribute == 2:
            liber_no_effect_at = self.state.get('liber_no_effect_at', 0)
            self.state = {'enter_status': 0, 'starflash_combo': 0, 'liberation': 0, 'outro': 0, 'priority_liberation_cast': 0}
            self.state['liber_no_effect_at'] = liber_no_effect_at

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
