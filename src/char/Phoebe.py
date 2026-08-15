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

    PHOEBE_BASE_STATE = {'enter_status': 0, 'starflash_combo': 0, 'liberation': 0, 'outro': 0, 'priority_liberation_cast': 0}

    def _reset_phoebe_state(self):
        """共用状态重置：__init__ 与 reset_state 各字段保持一致。"""
        self.attribute = 0
        self.star_available = False
        self.char_zani = None
        self.char_rover = None
        self.first_rotation_done = False
        self._zanfei_guang = False
        self._force_switch_me = False
        self._shou_full_tail_pending = False
        self._shou_full_tail_pending_at = 0
        self._shou_full_tail_force = False
        self.state = dict(self.PHOEBE_BASE_STATE)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attribute_mismatch = False
        self._reset_phoebe_state()

    def reset_state(self):
        # 跨战斗必须清掉抢大招成功标记，避免 pre-switch 误判 duplicate
        super().reset_state()
        self._reset_phoebe_state()

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
        """赞妮大招 phase2/3 落地即跑 insert 短轴（赞菲光/赞菲奶共用——token 由赞妮
        满协奏 force 切菲比时发放；无 token 的普通切人走常规轮转）。"""
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
        if self._shou_full_tail_pending:
            if not self._ensure_shou_full_tail():
                return None
            self._shou_full_tail_pending = False
            return self.switch_next_char(_zanfei_shou_full_tail=True)
        if self._in_zani_liber_insert_window():
            return self._do_liber_insert()
        return self._do_regular_rotation()

    def _prepare_regular_rotation(self):
        self.last_outro_time = -1
        start = time.time()
        if self.attribute == 0:
            self.decide_teammate()
        # 进场动画 >0.4s：star 缓存时立即抢 R 会 no-effect；动画由告解蓝条等待兜底
        self.sleep(0.01)
        if self.star_available:
            self.task.wait_until(self.down, time_out=2.0)
            self.sleep(0.3)
        if not self.has_intro:
            # 变奏入场先稳定进告解：大招动画后蓝环 UI 恢复竞态会进不去
            self._try_liberation_now()
        # 声骸 Q 改告解状态后、大招前释放（见 _do_regular_rotation 告解成功后 Q 插入点）
        return start

    def _resolve_linkage_or_exit(self):
        if self.flying():
            self.continues_normal_attack(0.1)
            return True, self.switch_next_char(), False
        attribute_mismatch = self.check_attribute_mismatch()
        if self.attribute == 2 and self.char_zani is not None:
            if not self.star_available:
                self.absolution_or_confession(wait_team=False)
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

    def _finish_regular_rotation(self):
        """切人前收尾（逐过程）：[非赞菲光补第 2 次 starflash] → 普攻到协奏 → 切人。
        （E 定身已移到 _do_regular_rotation 的 starflash 前）"""
        if self.attribute == 2:
            if not self._zanfei_guang:
                # 非赞菲光补第 2 次 starflash：2 层福音打 2 次重击；赞妮大招中/打不出不硬耗（普攻自然恢复）
                if self.state.get('starflash_combo', 0) < 2 and self.get_zani_state() != 1:
                    self.starflash_combo()
        elif self.attribute != 2:
            self.click_resonance(click_f=False)   # 变奏源模式：放掉已冷却的 E
        con_ready = self._ensure_first_rotation_con()
        return self.switch_next_char(
            _zanfei_full_tail=self._zanfei_guang,
            _zanfei_shou_full_tail=self.attribute == 2 and not self._zanfei_guang,
            _zanfei_con_ready=con_ready,
        )

    def _do_regular_rotation(self):
        start = self._prepare_regular_rotation()
        enter_before = self.state['enter_status']
        exited, result, attribute_mismatch = self._resolve_linkage_or_exit()
        if exited:
            return result
        wait_ui_time = 0.35 - (time.time() - start)
        if wait_ui_time > 0 and self.star_available and self.judge_forte() == 0:
            self.continues_normal_attack(wait_ui_time)
        if self.state['enter_status'] > enter_before:
            # 已进告解（开局 _resolve 先进告解）：跳过重复进——蓝条已熄，重复判定必失败白等
            status_entered = State.SUCCESS
        else:
            status_entered = self.absolution_or_confession(wait_team=False)
        self.check_combat()
        # 声骸 Q 告解状态后、大招前释放（告解形态伤害加成；outro 切走仍有 click_echo 兜底）
        if status_entered == State.SUCCESS and self.attribute == 2:
            self.click_echo(time_out=0)
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
        # E 定身（所有 starflash 前——非赞菲光每轮/赞菲光首轮）：短按 E 镜之环 2s 定怪方便重击，不会误进告解
        if self.attribute == 2 and (not self._zanfei_guang or not self.first_rotation_done):
            self.click_resonance(send_click=False, time_out=0.5, click_f=False)
            self.sleep(0.3)
        self._run_starflash_budget(status_entered)
        self._try_liberation_now()
        return self._finish_regular_rotation()

    def _do_liber_insert(self):
        """赞妮大招插入：赞菲奶=统一普攻 1.5s（变奏/非变奏入场都是）后切回；
        赞菲光=starflash 短轴（定身在后——重击后切回前定住怪，效果覆盖赞妮进场；
        定身在 starflash 前会在重击+切人等待中耗光 2s 效果）。
        不做告解/开大等前置（蓄力与长按动作时长本身覆盖切入动画；菲比大招留到 R2 后 do-perform 放）。"""
        self.logger.info('phoebe: zani liber insert short axis')
        if self.attribute == 0:
            self.decide_teammate()
        if not self._zanfei_guang:
            # 赞菲奶：等变奏落地（空中左键滑翔）→普攻 1.5s→切回；非变奏 wait_down 立即返回
            # 且 sleep 0.3 顺带覆盖进场动画
            self.task.wait_until(self.down, time_out=2.0)
            self.sleep(0.3)
            self.continues_normal_attack(1.5)
            return super().switch_next_char()
        # 贴脸切人短暂滞空：空中共鸣/大招 UI 变灰可由 down() 检测，零输入等落地再补 0.3s 稳定
        insert_start = time.time()
        self.task.wait_until(self.down, time_out=2.0)
        self.sleep(0.3)
        self.logger.info(f'phoebe: insert grounded wait elapsed={time.time() - insert_start:.2f}s')
        # 无条件调 starflash_combo：能直接重击就打，不能则充能段左键凑图标
        self.starflash_combo()
        self._ensure_grounded('insert after heavy')
        # 定身在 starflash 后：重击后切回前定住怪，效果覆盖赞妮进场（约 0.3s 生效）
        self.click_resonance(send_click=False, time_out=0.5, click_f=False)
        self.sleep(0.3)
        self._ensure_grounded('insert before switch')
        if self.buff_time > 0:
            self.last_buff_time = time.time()
            self.logger.info(f'phoebe: insert buff refreshed buff_time={self.buff_time}')
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
        # click_f=False：动画中每 0.1s 按 F 会打断 R 动画致 no-effect
        if self.click_liberation(send_click=send_click, click_f=False):
            self.state['liber_no_effect_at'] = 0
            return True
        self.logger.info(f'phoebe: liber no-effect, extended confirm{tag}')
        if self._confirm_liberation_transition('after extended wait', tag):
            return True
        if self.liberation_available():
            self.logger.info(f'phoebe: liber retry after no-effect{tag}')
            if self.click_liberation(send_click=send_click, click_f=False):
                self.state['liber_no_effect_at'] = 0
                return True
            if self._confirm_liberation_transition('after retry', tag):
                return True
        self._mark_liber_no_effect()
        return False

    def _attack_until_con(self, timeout, check_liber=True, interval=0.1):
        """普攻补协奏直到协奏满；满后若大招仍 pending 且可取/在 no-effect 恢复期，
        按 LIBER_HOLD_GRACE 有界留守（check_liber 时），超限或不可得即切。
        返回 True=协奏满过（视觉满 break），False=超时/留守退出未满。"""
        end = time.time() + timeout
        con_full_since = None
        con_full_seen = False
        while time.time() < end:
            if self.is_con_full():
                con_full_seen = True
                if con_full_since is None:
                    con_full_since = time.time()
                # 留守：大招仍 pending 可取/在恢复期且未超 LIBER_HOLD_GRACE
                if not (check_liber and self._liber_pending()):
                    break
                if time.time() - con_full_since >= self.LIBER_HOLD_GRACE:
                    break
                if not (self.liberation_available() or self._recent_liber_no_effect()):
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
        return con_full_seen

    def _ensure_first_rotation_con(self):
        """切人前补协奏：普攻到协奏满（上限 10s，满即 break；普攻中 R 可用可打断）。
        赞菲光必须磨满（死命令核心）；非赞菲光在赞妮大招中早退（大招中普攻无意义）。"""
        if not self.first_rotation_done:
            self.first_rotation_done = True
        allow_liber = bool(self.star_available)
        if not self._zanfei_guang and self.get_zani_state() == 1:
            return False
        return self._attack_until_con(10.0, check_liber=allow_liber)

    def zani_linkage(self):
        result = self.get_zani_state()
        # 先判赞妮大招中：blazes 常年 >=0.9，先判 blazes 会永远跳过 cast_remaining_skills/starflash
        if result == 1:
            self.cast_remaining_skills()
            return True
        if self.char_zani.blazes >= 0.9:
            # 停光噪前 star/重击已就绪先补 starflash，避免第二轮只普攻
            if self.star_available and (self.judge_forte() > 0 or self.is_forte_full()):
                self.starflash_combo()
            if not self.resonance_available():
                if result == 0 or self.char_zani.liberation_time_left() > 3:
                    self.continues_normal_attack(1, interval=0.15)
            elif not self._zanfei_guang and self.first_rotation_done and (not self.confession_ready()):
                self.click_resonance(send_click=False, click_f=False)
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
                if self.liberation_available() and self.click_liberation(send_click=False, click_f=False):
                    self.state['liberation'] += 1
            # 告解态 starflash 依赖重击就绪；仅判 prayer>0 会漏掉已可重击
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
        self.logger.debug(f'phoebe: judge_forte attribute={self.attribute} segments={forte}')
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

    def _charge_starflash_until_full(self, stop_on_condition=True):
        """左键单点直到重击图标亮（可打蓄力重击），最多 5s；无效（图标不亮）1s 即退。
        层数来源（用户机制 08-09）：长按 E 进告解自动满 2 层；重击消耗 1 层可保留。
        左键本身只是普攻（不产生层数），但重击图标亮起需要足够的普攻次数。
        stop_on_condition=True（starflash_combo 原行为）：prayer 条件满足即停；
        False（开大前保存满条）：只管充到满/无效退出——告解形态下蓝条在但不因 condition 提前停。"""
        start = time.time()
        check_forte = start
        condition = self.get_prayer_condition()
        recover_used = False
        recover_tried = False
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
                if (stop_on_condition and condition()) or self.judge_forte() == 0:
                    return recover_used
                check_forte = time.time()
            self.check_combat()
            self.task.next_frame()
        self.continues_right_click(0.05)
        return recover_used

    def starflash_combo(self):
        self.logger.info('perform starflash_combo')
        recover_used = False
        # 充能=左键到变蓝：不做 condition 前置/中断（前置判断会掐断第 2 段充能）
        if not self.is_forte_full():
            recover_used = self._charge_starflash_until_full(stop_on_condition=False)
        if self.star_available:
            # 不做蓝条重进保护：识别失败与真退出无法区分，误判重进是闪避后发呆主源
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
        self.logger.debug(f'phoebe: confession_ready blue_percent {blue_percent:.3f}')
        return blue_percent > 0.15

    def get_prayer_condition(self):
        if not self.check_middle_star():
            return self.is_forte_full
        if self.confession_ready():
            return self.confession_ready
        return lambda: False

    def absolution_or_confession(self, dodge_cancel=True, wait_team=True):
        if wait_team:
            self.task.wait_in_team_and_world(time_out=3, raise_if_not_found=False)
        condition = self.get_prayer_condition()
        if self.attribute == 2:
            key_down = lambda: self.task.send_key_down(self.get_resonance_key())
            key_up = lambda: self.task.send_key_up(self.get_resonance_key())
        else:
            key_down, key_up = (self.task.mouse_down, self.task.mouse_up)
        # 进场星 UI 先渲染、蓝条后渲染（0.2-0.5s）：有界等待蓝条出现，超时才判 unavailable
        if not condition():
            retry_start = time.time()
            while time.time() - retry_start < 2.0:
                if condition():
                    break
                self.sleep(0.2)
                self.task.next_frame()
        if condition():
            outer_start = time.time()
            while condition():
                if time.time() - outer_start > 2:
                    self.logger.info('phoebe: confession entry timeout')
                    return State.TIMEOUT
                key_down()
                key_hold_start = time.time()
                while condition() or time.time() - key_hold_start < 0.4:
                    if time.time() - key_hold_start > 1:
                        break
                    self.task.next_frame()
                key_up()
                if self.flying():
                    self.logger.debug('flying')
                    self.task.wait_until(lambda : not self.flying(),
                                         post_action=lambda : self.click(interval=0.1, after_sleep=0.1), time_out=2)
                    outer_start = time.time()
                self.task.next_frame()
            if self.attribute == 2:
                self.logger.info('Enters confession status')
                # 进入后福音回复满 2 段，段数 < 2 说明长按 E 未真正进入
            else:
                self.logger.info('Enters absolution status')
            if dodge_cancel:
                # 闪避等告解进入动作播完：立即闪避会打断动作/伤害致协奏慢（0.4s 偏短，放宽到 0.6s）
                self.sleep(0.6)
                self.continues_right_click(0.05)
            self.star_available = True
            self.reset_action()
            self._shou_full_tail_pending = False
            self._shou_full_tail_force = False
            self.state['enter_status'] += 1
            return State.SUCCESS
        self.logger.info(
            f'phoebe: confession entry unavailable star={self.star_available} '
            f'flying={self.flying()} intro={self.has_intro} att={self.attribute}'
        )
        return State.UNAVAILABLE

    def _try_liberation_now(self):
        """Try liberation immediately; True if cast succeeded."""
        if self.star_available and (not self.flying()) and self.liberation_available():
            if self._click_liberation_reliable(tag=' try-now'):
                self._record_liberation_cast()
                return True
        return False

    def _try_cast_liberation_before_switch(self):
        reason = None
        if self.attribute != 2:
            reason = 'attribute'
        elif self.state.get('priority_liberation_cast'):
            reason = 'duplicate'
        elif not self.star_available:
            reason = 'star-unavailable'
        elif self.flying():
            reason = 'airborne'
        elif not self.liberation_available():
            reason = 'liberation-unavailable'
        if reason is not None:
            return False
        if self._click_liberation_reliable(tag=' soft'):
            self._record_liberation_cast()
            return True
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

    def _block_switch_until_liber_resolved(self):
        """全满协奏切人前结算未决大招：先 2s 短结算（最多 3 次尝试），
        失败且仍 pending 时再 3.5s 有界重试（星失即停），都失败则放行切人。"""
        start = time.time()
        settled, attempts, result = self._resolve_pending_liberation(
            self.LIBER_SETTLE_TIMEOUT, ' settle', max_attempts=3
        )
        if settled:
            return True
        if not (self._liber_pending() and self.star_available):
            return False
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

    def _ensure_shou_full_tail(self):
        """Complete the authoritative Shou regular tail before allowing a switch."""
        if self.attribute != 2 or self._zanfei_guang:
            return True
        # 防 pending 死锁：R 释放失败无限重试会卡死战斗（in_combat 永真）；pending 超 15s 放弃强制切人
        if self._shou_full_tail_pending and time.time() - self._shou_full_tail_pending_at > 15.0:
            self.logger.info('phoebe: shou full-tail timeout 15s, force switch')
            self._shou_full_tail_pending = False
            self._shou_full_tail_force = True
            return True

        if not self.state.get('priority_liberation_cast'):
            self._try_liberation_now()

        for _ in range(2):
            if self.state.get('starflash_combo', 0) >= 2:
                break
            before = self.state.get('starflash_combo', 0)
            self.starflash_combo()
            if self.state.get('starflash_combo', 0) <= before:
                break

        if not self.state.get('priority_liberation_cast'):
            # 有界等 R（5s——能量不足时普攻攒能；不恢复直接切——保战斗不卡死）
            end_wait = time.time() + 5.0
            while time.time() < end_wait:
                self._try_liberation_now()
                if self.state.get('priority_liberation_cast'):
                    break
                self.click()
                self.task.next_frame()
            if not self.state.get('priority_liberation_cast'):
                self.logger.info('phoebe: shou full-tail R unavailable 5s, force switch')
                self._shou_full_tail_force = True
                return True

        liberation_done = bool(self.state.get('priority_liberation_cast'))
        starflash_done = self.state.get('starflash_combo', 0) >= 2
        return liberation_done and starflash_done

    def _prepare_exit(self, full_tail):
        self._try_cast_liberation_before_switch()
        if not (self.attribute == 2 and self.is_con_full() and full_tail and self._zanfei_guang):
            return
        self._block_switch_until_liber_resolved()

    def switch_next_char(self, *args, **kwargs):
        full_tail = bool(kwargs.pop('_zanfei_full_tail', False))
        shou_full_tail = bool(kwargs.pop('_zanfei_shou_full_tail', False))
        con_ready = bool(kwargs.pop('_zanfei_con_ready', False))
        self._prepare_exit(full_tail)
        if shou_full_tail and not self._shou_full_tail_force and not self._ensure_shou_full_tail():
            self._shou_full_tail_pending = True
            self._shou_full_tail_pending_at = time.time()
            return None
        self._shou_full_tail_pending = False
        self._shou_full_tail_force = False
        # is_con_full 在视觉已满时被 clamp 到 0.99（判定 False），用 current_con>=0.98 兑底；
        # 队里有 Zani 时 full-con 必须切回（unbuffed_support 优先会切奶妈）
        if self.attribute == 2 and (con_ready or self.is_con_full() or self.current_con >= 0.98):
            self.click_echo()
            self.state['outro'] += 1
            if self._zanfei_guang or self.char_zani is not None:
                return self._zanfei_switch_on_full_con()
        return super().switch_next_char(*args, **kwargs)

    def f_break(self, check_f_on_switch=False, force=False):
        """赞菲队（赞菲光/赞菲守）：菲比不做处决。
        菲比切走时 BaseCombatTask 会对 current_char.f_break(check_f_on_switch=True)
        F+左键连打触发处决动画 2.4s，
        清空赞妮大招重击条致 phase3 动作丢失（夜闪/打砸不执行直接 R2）。"""
        return False

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
        # 同 Zani.decide_teammate：赞菲光下光主为局部 SubDps，便于默认切人进 buff 池
        if self._zanfei_guang and self.char_rover is not None:
            self.char_rover.set_char_type(CharType.SUB_DPS)
            # 同 Zani：工厂 buff_time=0 已标记 configured，必须显式设 14 才能进 buff 池
            self.char_rover.set_buff_time(14)
            self.logger.info(
                f'phoebe: zanfei Rover local SubDps char_type={self.char_rover.char_type} '
                f'buff_time={self.char_rover.buff_time}'
            )

    def judge_amplitude(self, gray, min_amp):
        height, width = gray.shape
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
            self.state = dict(self.PHOEBE_BASE_STATE)
            self.state['liber_no_effect_at'] = liber_no_effect_at

    def is_forte_full(self):
        if not self.star_available:
            return super().is_forte_full()
        return self.is_mouse_forte_full()

    def shorekeeper_auto_dodge(self):
        from src.char.ShoreKeeper import ShoreKeeper
        for char in self.task.chars:
            if isinstance(char, ShoreKeeper):
                return char.auto_dodge(condition = self.flying)

phoebe_blue_color = {
    'r': (124, 134),
    'g': (176, 186),
    'b': (250, 255)
}

phoebe_light_color = {
    'r': (250, 255),
    'g': (250, 255),
    'b': (175, 185)
}

phoebe_forte_light_color = {
    'r': (240, 255),
    'g': (240, 255),
    'b': (165, 195)
}

phoebe_forte_blue_color = {
    'r': (225, 255),
    'g': (225, 255),
    'b': (190, 225)
}

phoebe_star_light_color = {
    'r': (235, 255),
    'g': (220, 250),
    'b': (160, 190)
}

phoebe_star_blue_color = {
    'r': (240, 255),
    'g': (240, 255),
    'b': (240, 255)
}
