import time
import cv2
import numpy as np
from enum import Enum
from src.char.BaseChar import BaseChar, CharType, SwitchPriority
from ok import color_range_to_bound

class State(Enum):
    SUCCESS = 1
    UNAVAILABLE = 2

class Phoebe(BaseChar):

    PHOEBE_BASE_STATE = {'enter_status': 0, 'starflash_combo': 0, 'liberation': 0, 'outro': 0, 'priority_liberation_cast': 0}
    FORM_CHARGE_CAPACITY = {1: 4, 2: 2}
    CONCERT_FILL_END = 'concert-fill end'

    def _invalidate_form_charges(self):
        self.remaining_charges = 0
        self._charge_attribute = None

    def _form_charge_capacity(self):
        return self.FORM_CHARGE_CAPACITY.get(self.attribute)

    def _known_form_charges(self):
        if self.remaining_charges > 0 and self._charge_attribute != self.attribute:
            self._invalidate_form_charges()
        return self.remaining_charges

    def _refill_form_charges(self):
        self.remaining_charges = self._form_charge_capacity() or 0
        self._charge_attribute = self.attribute if self.remaining_charges > 0 else None

    def _consume_form_charge(self):
        charges = self._known_form_charges()
        if charges > 0:
            self.remaining_charges = charges - 1
        if self.remaining_charges == 0:
            self._charge_attribute = None

    def _reset_phoebe_state(self):
        """共用状态重置：__init__ 与 reset_state 各字段保持一致。"""
        self.attribute = 0
        self.star_available = False
        self.char_zani = None
        self.char_rover = None
        self.first_rotation_done = False
        self.team = 0  # 1=赞菲光 2=赞菲守 3=卡提+光主 0=其他
        self._rover_form_pending = False
        self._zanfei_guang = False
        self._invalidate_form_charges()
        self._force_switch_me = False
        self.state = dict(self.PHOEBE_BASE_STATE)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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

    def _trace(self, event, **details):
        fields = ' '.join(f'{key}={value}' for key, value in details.items())
        self.logger.info(f'phoebe: trace {event}' + (f' {fields}' if fields else ''))

    def _select_perform_axis(self):
        """Token Insert 优先；无 token 的赞妮大招回切才走 handoff（赞菲光）。"""
        if self.team == 0 or self._rover_form_pending:
            self.decide_teammate()
        if self._in_zani_liber_insert_window():
            return 'insert'
        zani_liberating = self.char_zani is not None and self.char_zani.get_state() == 1
        return 'handoff' if zani_liberating else 'regular'

    def _do_zani_liber_handoff(self):
        """赞妮大招无 token 回切：不消耗菲比资源，立即交还赞妮。"""
        self.logger.info('phoebe: zani liber handoff short axis')
        starflash_before = self.state['starflash_combo']
        charges_before = self.remaining_charges
        self._trace('handoff begin', star=self.star_available, charges=charges_before)
        self._trace('handoff residual=skipped', reason='no-token-liberation')
        self._trace(
            'handoff verify', starflash_delta=self.state['starflash_combo'] - starflash_before,
            charge_delta=self.remaining_charges - charges_before,
        )
        self._trace('handoff input=force-switch-zani')
        return self._force_switch_to(self.char_zani)

    def _in_zani_liber_insert_window(self):
        """赞妮大招 phase2/3 落地即跑 insert 短轴。赞菲光：token 命中才进（starflash+定身+切回）；
        赞菲奶：赞妮大招中即进（只定身+切回，无 token 需求）。
        team 由 _select_perform_axis 统一刷新。"""
        zani = self.char_zani
        if zani is None:
            from src.char.Zani import Zani
            zani = self.task.has_char(Zani)
            self.char_zani = zani
        if zani is None:
            return False
        if self.team == 1:
            return bool(zani.try_consume_insert_handoff())
        if self.team == 2:
            # 赞菲奶：赞妮大招中即进 insert（无 token；进场即定身一次再切回）
            return zani.get_state() == 1
        return False

    def do_perform(self):
        self._trace(
            'perform-begin', attribute=self.attribute, intro=self.has_intro,
            star=self.star_available, charges=self.remaining_charges,
        )
        axis = self._select_perform_axis()
        self.logger.info(
            f'phoebe: axis={axis} team={self.team} attribute={self.attribute} '
            f'zanfei_guang={self._zanfei_guang} intro={self.has_intro} '
            f'star={self.star_available} charges={self.remaining_charges}'
        )
        if axis == 'insert':
            return self._do_liber_insert()
        if axis == 'handoff':
            return self._do_zani_liber_handoff()
        return self._do_regular_rotation()

    def _prepare_regular_rotation(self):
        self.last_outro_time = -1
        start = time.time()
        self._trace('regular-prepare begin', intro=self.has_intro, star=self.star_available)
        # team 由 _select_perform_axis 统一刷新（team==0 → decide_teammate）
        # 进场动画 >0.4s：star 缓存时立即抢 R 会 no-effect；动画由告解蓝条等待兜底
        self._trace('regular-prepare input=sleep', duration=0.01)
        self.sleep(0.01)
        if self.star_available:
            self._trace('regular-prepare input=wait-down', timeout=2.0)
            down_ready = self.task.wait_until(self.down, time_out=2.0)
            self._trace('regular-prepare wait-down result', ready=down_ready,
                        elapsed=f'{time.time() - start:.2f}')
            self._trace('regular-prepare input=sleep', duration=0.3)
            self.sleep(0.3)
        self._trace('regular-prepare end', elapsed=f'{time.time() - start:.2f}')
        # 声骸 Q 改告解状态后、大招前释放（见 _do_regular_rotation 告解成功后 Q 插入点）
        return start

    def _resolve_linkage_or_exit(self):
        if self.flying():
            self.continues_normal_attack(0.1)
            return True, self.switch_next_char()
        if self.attribute == 2 and self._should_handoff_to_zani():
            self._run_zani_linkage_handoff()
            return True, self.switch_next_char()
        return False, None

    def _try_liberation_after_starflash(self, starflash_before, tag):
        """每次确认星闪后唯一的后续 R 窗口。"""
        cast = self.state['starflash_combo'] > starflash_before
        self._trace('starflash liberation-window', tag=tag, cast=cast,
                    count=self.state['starflash_combo'])
        if (
            cast
            and not self.state.get('priority_liberation_cast')
            and self.star_available
            and not self.flying()
            and self.liberation_available()
            and self._click_liberation_reliable(tag=f' {tag}')
        ):
            self._record_liberation_cast()
            self._trace('starflash liberation-window result=cast', tag=tag)
            return True
        return False

    def _run_starflash_budget(self, status_entered):
        zanfei_support_fallback = bool(
            self.team == 1 and self.attribute == 2 and self.star_available
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
        starflash_before = self.state['starflash_combo']
        self.starflash_combo()
        self._try_liberation_after_starflash(starflash_before, 'budget')

    def _finish_regular_rotation(self):
        """切人前收尾（逐过程）：[非赞菲光补第 2 次 starflash] → 普攻到协奏 → 切人。
        （E 定身已移到 _do_regular_rotation 的 starflash 前）"""
        self._trace('regular-finish begin', attribute=self.attribute,
                    starflash_count=self.state.get('starflash_combo', 0))
        if self.attribute == 2:
            if self.team != 1:
                # 非赞菲光补第 2 次 starflash：2 层福音打 2 次重击；赞妮大招中/打不出不硬耗（普攻自然恢复）
                if self.state.get('starflash_combo', 0) < 2 and self.get_zani_state() != 1:
                    self._trace('regular-finish action=second-starflash begin')
                    starflash_before = self.state['starflash_combo']
                    self.starflash_combo()
                    self._try_liberation_after_starflash(starflash_before, 'second-starflash')
                    self._trace('regular-finish action=second-starflash end',
                                count=self.state.get('starflash_combo', 0))
        elif self.attribute != 2:
            self._trace('regular-finish input=short-E-release')
            self.click_resonance(click_f=False)   # 变奏源模式：放掉已冷却的 E
        self._trace('regular-finish action=concert-fill begin')
        con_ready = self._ensure_first_rotation_con()
        self._trace('regular-finish action=concert-fill result', con_ready=con_ready,
                    con=f'{self.get_current_con():.3f}')
        if con_ready is None:
            self._trace('regular-finish result=out-of-combat')
            return None
        self._trace('regular-finish input=switch', con_ready=con_ready)
        return self.switch_next_char(
            _zanfei_full_tail=self.team == 1,
            _zanfei_con_ready=con_ready,
        )

    def _do_regular_rotation(self):
        self._trace('regular begin', intro=self.has_intro, star=self.star_available,
                    charges=self.remaining_charges, entered=self.state['enter_status'])
        start = self._prepare_regular_rotation()
        self._trace('regular entry-ready', delay=f'{time.time() - start:.2f}')
        self._trace('regular action=linkage-resolve begin')
        exited, result = self._resolve_linkage_or_exit()
        self._trace('regular action=linkage-resolve result', exited=exited)
        if exited:
            return result
        if not self.has_intro and self.star_available and (not self.flying()) and self.liberation_available():
            self._trace('regular-prepare input=liberation', available=True)
            if self._click_liberation_reliable(tag=' prepare'):
                self._record_liberation_cast()
        wait_ui_time = 0.35 - (time.time() - start)
        if wait_ui_time > 0 and self.star_available and self.judge_forte() == 0:
            self._trace('regular input=normal-attack-wait', duration=f'{wait_ui_time:.2f}')
            self.continues_normal_attack(wait_ui_time)
        self.logger.info('phoebe: entry caller=regular-form')
        self._trace('regular action=form-entry begin', caller='regular-form')
        status_entered = self.absolution_or_confession(wait_team=False)
        self.logger.info(f'phoebe: entry caller=regular-form result={status_entered}')
        self._trace('regular action=form-entry result', result=status_entered)
        self.check_combat()
        # 声骸 Q 告解状态后、大招前释放（告解形态伤害加成；outro 切走仍有 click_echo 兜底）
        if status_entered == State.SUCCESS and self.attribute == 2:
            self._trace('regular input=echo-Q begin')
            echo_result = self.click_echo(time_out=0)
            self._trace('regular input=echo-Q result', result=echo_result)
        if self.star_available:
            blue_required = self.team in (1, 2)
            blue_ready = not blue_required
            if blue_required and self.state.get('priority_liberation_cast'):
                self._trace('regular action=liberation skipped', reason='already-cast')
            else:
                if blue_required:
                    self._charge_starflash_until_full(
                        finish_with_right_click=False, interval_click=True
                    )
                    blue_ready = self.is_forte_full()
                if blue_ready:
                    self._trace('regular action=liberation begin', tag='do-perform')
                    if self._click_liberation_reliable(tag=' do-perform', require_forte_retry=blue_required):
                        self._record_liberation_cast()
                        self._trace('regular action=liberation result', result='cast')
                    elif (
                        not self.state.get('priority_liberation_cast')
                        and self.liberation_available()
                        and not self.flying()
                    ):
                        if blue_required:
                            self._charge_starflash_until_full(
                                finish_with_right_click=False, interval_click=True
                            )
                            blue_ready = self.is_forte_full()
                        if blue_ready:
                            self._trace('regular action=liberation retry', tag='do-perform-retry')
                            if self._click_liberation_reliable(
                                tag=' do-perform-retry', require_forte_retry=blue_required
                            ):
                                self._record_liberation_cast()
                                self._trace('regular action=liberation retry-result', result='cast')
                elif blue_required:
                    self._trace('regular action=liberation skipped', reason='forte-not-ready')
        # E 定身（所有 starflash 前——仅首轮）：短按 E 镜之环 2s 定怪方便重击，不会误进告解
        if self.attribute == 2 and not self.first_rotation_done:
            self._trace('regular input=short-E-control begin')
            self.click_resonance(send_click=False, time_out=0.5, click_f=False)
            self._trace('regular input=short-E-control sleep', duration=0.3)
            self.sleep(0.3)
        self._trace('regular action=starflash-budget begin', status=status_entered)
        self._run_starflash_budget(status_entered)
        self._trace('regular action=starflash-budget end', count=self.state['starflash_combo'])
        self._trace('regular action=finish begin')
        return self._finish_regular_rotation()

    def _do_liber_insert(self):
        """赞妮大招插入：切入后立即 starflash 蓄力重击（图标亮直接打，不亮由充能段
        左键凑图标——给赞妮回能量）→ 短按 E 定身（重击后切回前定住怪，效果覆盖
        赞妮进场）→ 切回。赞菲奶简版：只放一个定身便交还赞妮（不 starflash/不补资源）。
        不做告解/开大等前置（蓄力与长按动作时长本身覆盖切入动画；菲比大招留到
        R2 后 do-perform 放）。"""
        self.logger.info('phoebe: zani liber insert short axis')
        # team/attribute 由 _select_perform_axis 统一刷新（赞菲光 token / 赞菲奶大招中）
        # 贴脸切人短暂滞空：空中共鸣/大招 UI 变灰可由 down() 检测，零输入等落地再补 0.3s 稳定
        insert_start = time.time()
        self.task.wait_until(self.down, time_out=2.0)
        self.sleep(0.3)
        self.logger.info(f'phoebe: insert grounded wait elapsed={time.time() - insert_start:.2f}s')
        if self.team == 2:
            # 赞菲奶 insert 简版：等变奏入场动画剩余预算（down 图标可用≠动画解锁，
            # 动画期中短按 E 会被游戏吞掉——G1 同根），再放一个定身（镜之环短按 E）交还赞妮
            budget_remaining = 0.0
            budget_applied = False
            if self.last_switch_in_time > 0:
                remaining = self.intro_motion_freeze_duration - (time.time() - self.last_switch_in_time)
                if remaining > 0:
                    budget_remaining = remaining
                    budget_applied = True
                    self.sleep(remaining, check_combat=False)
            self.logger.info(
                f'phoebe: insert intro-budget remaining={budget_remaining:.2f} '
                f'applied={budget_applied}'
            )
            self._insert_control_e()
        else:
            # 无条件调 starflash_combo：能直接重击就打，不能则充能段左键凑图标
            self.starflash_combo()
            self._ensure_grounded('insert after heavy')
            # 定身在 starflash 后：重击后切回前定住怪，效果覆盖赞妮进场（约 0.3s 生效）
            self._insert_control_e()
        self._ensure_grounded('insert before switch')
        if self.buff_time > 0:
            self.last_buff_time = time.time()
            self.logger.info(f'phoebe: insert buff refreshed buff_time={self.buff_time}')
        return super().switch_next_char()

    def _insert_control_e(self):
        """Insert 重击后的短按 E 定身；UI 检测未发键时补一次受控短按。"""
        self._trace('insert control-E begin', available=self.resonance_available())
        clicked, duration, animated = self.click_resonance(
            send_click=False, time_out=0.5, click_f=False
        )
        self._trace(
            'insert control-E result', clicked=clicked,
            duration=f'{duration:.2f}', animated=animated,
        )
        if not clicked:
            # 星闪刚清图标的瞬间可让共鸣 UI 迟一帧恢复；只补一次短按，绝不长按进形态。
            self.send_resonance_key()
            self._trace('insert control-E fallback=short-key')
        self.sleep(0.3)
        return clicked

    def _ensure_grounded(self, tag=''):
        """落地等待：滞空时 wait_down，仍飞则限时点击辅助落地（点击仅为落地，不构成输出）。"""
        if not self.flying():
            return
        self.wait_down()
        if self.flying():
            self.logger.info(f'phoebe: wait land {tag}')
            self.task.wait_until(lambda : not self.flying(), post_action=lambda : self.click(interval=0.1, after_sleep=0.05), time_out=2.0)
            self.wait_down()

    def _hold_resonance_key(self, duration):
        """长按共鸣键 duration 秒（next_frame 等待）。形态进入与 recovery 共用。"""
        key = self.get_resonance_key()
        self.task.send_key_down(key)
        hold_start = time.time()
        while time.time() - hold_start < duration:
            self.task.next_frame()
        self.task.send_key_up(key)

    LIBER_HOLD_GRACE = 3.0
    LIBER_NO_EFFECT_HOLD = 2.0
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

    def _click_liberation_reliable(self, send_click=True, tag='', require_forte_retry=False):
        """Base no-effect is only a 0.4s animation miss - confirm longer and retry once.
        Q 后赞菲光主窗口可要求内部 retry 也先重新点亮蓝色重击图标。"""
        # click_f=False：动画中每 0.1s 按 F 会打断 R 动画致 no-effect
        self._trace('liberation input=click', tag=tag.strip(), available=self.liberation_available())
        if self.click_liberation(send_click=send_click, click_f=False):
            self.state['liber_no_effect_at'] = 0
            self._trace('liberation result=cast', tag=tag.strip())
            return True
        self.logger.info(f'phoebe: liber no-effect, extended confirm{tag}')
        self._trace('liberation result=no-effect', tag=tag.strip())
        if self._confirm_liberation_transition('after extended wait', tag):
            self._trace('liberation result=confirmed-after-wait', tag=tag.strip())
            return True
        if self.liberation_available():
            if require_forte_retry:
                self._charge_starflash_until_full(
                    finish_with_right_click=False, interval_click=True
                )
                if not self.is_forte_full():
                    self._trace('liberation retry skipped', tag=tag.strip(), reason='forte-not-ready')
                    self._mark_liber_no_effect()
                    return False
            self.logger.info(f'phoebe: liber retry after no-effect{tag}')
            self._trace('liberation input=retry', tag=tag.strip())
            if self.click_liberation(send_click=send_click, click_f=False):
                self.state['liber_no_effect_at'] = 0
                self._trace('liberation result=cast-retry', tag=tag.strip())
                return True
            if self._confirm_liberation_transition('after retry', tag):
                self._trace('liberation result=confirmed-after-retry', tag=tag.strip())
                return True
        self._mark_liber_no_effect()
        self._trace('liberation result=failed', tag=tag.strip())
        return False

    def _attack_until_con(self, timeout, check_liber=True, interval=0.1, require_forte=False):
        """普攻补协奏直到协奏满；赞菲光收尾额外要求星闪重击图标亮。
        满后若大招仍 pending 且可取/在 no-effect 恢复期，按 LIBER_HOLD_GRACE
        有界留守（check_liber 时），超限或不可得即切。返回 True=离场条件达成、
        False=未达成、None=补协奏期间已脱战（调用方不得再切人）。"""
        end = time.time() + timeout
        con_full_since = None
        exit_ready_seen = False
        combat_ended = False
        attacks = 0
        self._trace('concert-fill begin', timeout=timeout, require_forte=require_forte,
                    check_liber=check_liber)
        while time.time() < end:
            if hasattr(self.task, 'in_combat') and not self.task.in_combat():
                combat_ended = True
                self._trace(self.CONCERT_FILL_END, reason='out-of-combat', attacks=attacks)
                break
            current_con = self.get_current_con()
            con_full = current_con >= 1.0
            forte_ready = self.is_forte_full() if require_forte else None
            exit_ready = con_full and (not require_forte or forte_ready)
            if exit_ready:
                exit_ready_seen = True
                if con_full_since is None:
                    con_full_since = time.time()
                    self._trace('concert-fill exit-condition-met', con=f'{current_con:.3f}', forte=forte_ready)
                # 留守：大招仍 pending 可取/在恢复期且未超 LIBER_HOLD_GRACE
                if not (check_liber and self._liber_pending()):
                    self._trace(self.CONCERT_FILL_END, reason='exit-ready', attacks=attacks)
                    break
                if time.time() - con_full_since >= self.LIBER_HOLD_GRACE:
                    self._trace(self.CONCERT_FILL_END, reason='liber-grace-expired', attacks=attacks)
                    break
                if not (self.liberation_available() or self._recent_liber_no_effect()):
                    self._trace(self.CONCERT_FILL_END, reason='liber-unavailable', attacks=attacks)
                    break
            else:
                con_full_since = None
            if check_liber and not self.state.get('priority_liberation_cast') and self.star_available and (not self.flying()) and (
                self.liberation_available() or self._recent_liber_no_effect()
            ):
                if self.liberation_available():
                    self._trace('concert-fill action=liberation', attacks=attacks)
                    if self._click_liberation_reliable(tag=' attack-con'):
                        self._record_liberation_cast()
                        continue
            if attacks == 0:
                self._trace('concert-fill input=normal-attack')
            self.task.click()
            attacks += 1
            self.sleep(interval)
        if not combat_ended and hasattr(self.task, 'in_combat') and not self.task.in_combat():
            combat_ended = True
            self._trace(self.CONCERT_FILL_END, reason='out-of-combat', attacks=attacks)
        elif time.time() >= end and not exit_ready_seen:
            self._trace(self.CONCERT_FILL_END, reason='timeout', attacks=attacks)
        return None if combat_ended else exit_ready_seen

    def _ensure_first_rotation_con(self):
        """切人前普攻补条件：协奏满；赞菲光额外要保留可直接重击的星闪图标。
        仍保留 10 秒防死锁上限，普攻中 R 可用可打断。"""
        if not self.first_rotation_done:
            self.first_rotation_done = True
        allow_liber = bool(self.star_available)
        if self.team != 1 and self.get_zani_state() == 1:
            return False
        return self._attack_until_con(
            10.0, check_liber=allow_liber, require_forte=self.team == 1
        )

    def _should_handoff_to_zani(self):
        """只读判断：赞妮资源已满时将场上控制权立即交还。"""
        return self.char_zani is not None and self.char_zani.blazes >= 0.9

    def _run_zani_linkage_handoff(self):
        """执行既有赞妮短收尾；调用方负责随后安全切人。"""
        result = self.get_zani_state()
        # 停光噪前 star/重击已就绪先补 starflash，避免第二轮只普攻
        if self.star_available and (self.judge_forte() > 0 or self.is_forte_full()):
            self.starflash_combo()
        if not self.resonance_available():
            if result == 0 or self.char_zani.liberation_time_left() > 3:
                self.continues_normal_attack(1, interval=0.15)
        elif self.team != 1 and self.first_rotation_done and (not self.confession_ready()):
            self.click_resonance(send_click=False, click_f=False)
        return True

    def judge_forte(self):
        box = self.task.box_of_screen_scaled(3840, 2160, 1633, 2004, 2160, 2014, name='phoebe_forte1', hcenter=True)
        if self.attribute == 1:
            forte = self.calculate_forte_num(phoebe_forte_light_color, box, 4, 25)
        else:
            forte = self.calculate_forte_num(phoebe_forte_blue_color, box, 2, 50)
        self.logger.debug(f'phoebe: judge_forte attribute={self.attribute} segments={forte}')
        return forte

    STARFLASH_RECOVER_AFTER = 2.0

    def _starflash_recover_with_e(self, finish_with_right_click=True):
        """乱轴后主动长按 E + 后撑，把自己拉回 starflash 状态。"""
        if not self.resonance_available():
            self.logger.info('phoebe: starflash recover skip, E not ready')
            self._trace('starflash-recover result=skip', reason='E-not-ready')
            return False
        self.logger.info('phoebe: starflash recover long-press E + backstep')
        self._trace('starflash-recover input=long-E begin', hold=0.55)
        self._hold_resonance_key(0.55)
        self.sleep(0.05)
        self._trace('starflash-recover input=long-E end')
        self._trace('starflash-recover action=ensure-grounded begin')
        self._ensure_grounded('starflash recover')
        if self.flying():
            self._invalidate_form_charges()
            self._trace('starflash-recover result=failed', reason='still-flying')
            return False
        self._refill_form_charges()
        if finish_with_right_click:
            self._trace('starflash-recover input=right-click', duration=0.1)
            self.continues_right_click(0.1)
        self._trace('starflash-recover result=success', charges=self.remaining_charges,
                    finish_with_right_click=finish_with_right_click)
        return True

    def _charge_starflash_until_full(self, finish_with_right_click=True, interval_click=False):
        """左键单点直到重击图标亮，最多 5s；可选以右键完成星闪。
        开始时刷新一次星色。
        finish_with_right_click=False 仅为赞菲光常规 Q 后 R 窗口充蓝，
        interval_click=True 时复用 R 确认期的节流左键；默认保留原星闪节奏。"""
        start = time.time()
        self.check_middle_star()
        recover_used = False
        recover_tried = False
        attacks = 0
        self._trace('starflash-charge begin', forte=self.is_forte_full(),
                    charges=self.remaining_charges)
        while not self.is_forte_full():
            if self.flying():
                self._trace('starflash-charge action=auto-dodge-airborne')
                self.shorekeeper_auto_dodge()
            if attacks == 0:
                self._trace('starflash-charge input=normal-attack')
            (self.click_with_interval if interval_click else self.click)()
            attacks += 1
            elapsed = time.time() - start
            if elapsed > 5:
                self._trace('starflash-charge end', reason='timeout', attacks=attacks,
                            recover_used=recover_used,
                            in_combat=hasattr(self.task, 'in_combat') and self.task.in_combat(),
                            forte=self.is_forte_full())
                return recover_used
            if (
                not recover_tried
                and self.team == 1
                and elapsed > self.STARFLASH_RECOVER_AFTER
            ):
                recover_tried = True
                self._trace('starflash-charge action=recover-E begin', elapsed=f'{elapsed:.2f}')
                if self._starflash_recover_with_e(finish_with_right_click=finish_with_right_click):
                    recover_used = True
                    self.task.next_frame()
                    continue
            self.check_combat()
            self.task.next_frame()
        if finish_with_right_click:
            self._trace('starflash-charge input=right-click', duration=0.05, attacks=attacks)
            # 收尾右键=闪避。不用 continues_right_click(0.05)：其内部 click(interval=0.1)
            # 会被 check_interval 节流吞掉（距上次普攻 <0.1s → 不发出且 reset_scene 清帧），
            # 导致 starflash_combo 重击门前被迫现场截图拍到普攻尾帧 → 图标未亮 → 静默 not-cast。
            # 直接 task.click(key='right') 不节流：右键一定发出且保留已亮的旧帧。
            self.task.click(key='right')
        self._trace('starflash-charge end', reason='forte-ready', attacks=attacks,
                    recover_used=recover_used, finish_with_right_click=finish_with_right_click)
        return recover_used

    def starflash_combo(self):
        self.logger.info('perform starflash_combo')
        self._trace('starflash begin', forte=self.is_forte_full(), star=self.star_available,
                    charges=self.remaining_charges, count=self.state['starflash_combo'])
        recover_used = False
        # 充能=左键到变蓝：不做 condition 前置/中断（前置判断会掐断第 2 段充能）
        if not self.is_forte_full():
            recover_used = self._charge_starflash_until_full()
        if self.star_available:
            # 不做蓝条重进保护：识别失败与真退出无法区分，误判重进是闪避后发呆主源
            if self.is_forte_full():
                cast = False
                flying = False
                outer_start = time.time()
                attempts = 0
                while self.is_forte_full():
                    if time.time() - outer_start > 2:
                        self._trace('starflash heavy end', reason='outer-timeout', attempts=attempts)
                        break
                    attempts += 1
                    self._trace('starflash heavy input=mouse-down', attempt=attempts, hold=0.5)
                    self.task.mouse_down()
                    mouse_hold_start = time.time()
                    while time.time() - mouse_hold_start < 0.5:
                        if not self.is_forte_full():
                            cast = True
                            self._trace('starflash heavy result=cast-detected', attempt=attempts)
                            break
                        if flying := self.flying():
                            self._trace('starflash heavy result=airborne', attempt=attempts)
                            break
                        self.task.next_frame()
                    self._trace('starflash heavy input=mouse-up', attempt=attempts)
                    self.task.mouse_up()
                    if flying:
                        self._ensure_grounded('starflash heavy')
                        outer_start = time.time()
                    self.check_combat()
                    self.task.next_frame()
                else:
                    cast = True
                    self._trace('starflash heavy result=cast-icon-cleared', attempts=attempts)
                if cast:
                    self.state['starflash_combo'] += 1
                    self._consume_form_charge()
                    self._trace('starflash end', result='cast', count=self.state['starflash_combo'],
                                charges=self.remaining_charges, recover_used=recover_used)
                    return recover_used
        self._trace('starflash end', result='not-cast', recover_used=recover_used,
                    forte=self.is_forte_full(), star=self.star_available)
        return recover_used

    def confession_ready(self):
        box = self.task.box_of_screen_scaled(2560, 1440, 2110, 1236, 2217, 1343, name='phoebe_resonance', hcenter=False)
        self.task.draw_boxes(box.name, box)
        from src.char.Zani import Zani
        blue_percent = Zani.calculate_color_percentage_in_masked(self, phoebe_blue_color, box, 0.425, 0.490)
        self.logger.debug(f'phoebe: confession_ready blue_percent {blue_percent:.3f}')
        return blue_percent > 0.15

    def absolution_or_confession(self, dodge_cancel=True, wait_team=True):
        if wait_team:
            self.task.wait_in_team_and_world(time_out=3, raise_if_not_found=False)
        charges = self._known_form_charges()
        if charges is not None and charges > 0:
            self.star_available = True
            return State.SUCCESS
        # 两态资源：正数直接复用，0 无条件固定长按补满。
        self.logger.info(f'phoebe: entry begin charges={charges} att={self.attribute}')
        # 固定长按 1.2s：is_forte_full 双语义（star_available 时=重击图标找图）——
        # 辅助形态进场图标灭（星闪后充能 0+次数不够）→ 立即退出致没长按（0.003s 假 SUCCESS 实锤）；
        # 1.2s 固定按住保证游戏长按判定（短按=定身+传送）；切辅助/恢复充能均在按住期间完成
        hold_started_at = time.time()
        self.logger.info('phoebe: entry hold-start')
        if self.attribute == 2:
            # E 长按复用共享原语（next_frame 等待，与 recovery 长按一致）
            self._hold_resonance_key(1.2)
        else:
            self.task.mouse_down()
            self.sleep(1.2)
            self.task.mouse_up()
        self.logger.info(f'phoebe: entry hold-release elapsed={time.time() - hold_started_at:.2f}s')
        if self.flying():
            self.logger.info('phoebe: entry airborne-after-hold')
            self.task.wait_until(lambda : not self.flying(),
                                 post_action=lambda : self.click(interval=0.1, after_sleep=0.1), time_out=2)
        if self.flying():
            self.logger.info('phoebe: entry failed-still-airborne')
            self._invalidate_form_charges()
            return State.UNAVAILABLE
        if self.attribute == 2:
            self.logger.info('Enters confession status')
        else:
            self.logger.info('Enters absolution status')
        if dodge_cancel:
            # EXPERIMENT: send dodge immediately after a confirmed form entry.
            self.logger.info('phoebe: entry dodge-settle-start duration=0.00 experiment=no-settle')
            self.logger.info('phoebe: entry dodge-right-click')
            self.continues_right_click(0.05)
            self.logger.info('phoebe: entry dodge-finished')
        self.star_available = True
        self.reset_action(new_rotation=False)
        self._refill_form_charges()
        self.state['enter_status'] += 1
        return State.SUCCESS

    def switch_next_char(self, *args, **kwargs):
        full_tail = bool(kwargs.pop('_zanfei_full_tail', False))
        con_ready = bool(kwargs.pop('_zanfei_con_ready', False))
        self._trace('switch begin', full_tail=full_tail, con_ready=con_ready)
        # 切人出口不再尝试 R；R 只属于 Q、星闪或补资源窗口
        self._trace('switch prepare-exit', full_tail=full_tail,
                    liberation=bool(self.state.get('priority_liberation_cast')))
        # >=1.0 兑底：视觉满（含超采样）才切，视觉 98-99% 不切（继续补协奏）；
        # get_current_con() 才更新字段——直接读字段恒为 0（进场重置后从不采样）
        # 队里有 Zani 时 full-con 必须切回（unbuffed_support 优先会切奶妈）
        if self.team in (1, 2) and (con_ready or self.is_con_full() or self.get_current_con() >= 1.0):
            self.logger.info(
                f'phoebe: switch to Zani con_ready={con_ready} is_con_full={self.is_con_full()} '
                f'current_con={self.get_current_con():.4f}'
            )
            self._trace('switch input=echo-Q-outro')
            self.click_echo()
            self.state['outro'] += 1
            self._trace('switch input=force-zani')
            return self._zanfei_switch_on_full_con()
        self._trace('switch input=base-selector')
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
        from src.char.Rover import Rover
        self.char_rover = self.task.has_char(Rover)
        rover_form = (
            self.task.get_known_ring_index(self.char_rover)
            if self.char_rover is not None and hasattr(self.task, 'get_known_ring_index')
            else getattr(self.char_rover, 'ring_index', -1)
        )
        self._rover_form_pending = self.char_rover is not None and rover_form < 0
        if char := self.task.has_char(Zani):
            self.char_zani = char
            self.team = 1 if self.char_rover else 2
        elif self.task.has_char(Cartethyia) and self.char_rover:
            self.team = 3
        else:
            self.team = 0
        self._zanfei_guang = self.team == 1
        self.attribute = 2 if self.team in (1, 2, 3) else 1
        if self.team == 1 and self.char_rover is not None:
            self.char_rover.set_char_type(CharType.SUB_DPS)
            self.char_rover.set_buff_time(14)
            self.logger.info(
                f'phoebe: zanfei Rover local SubDps char_type={self.char_rover.char_type} '
                f'buff_time={self.char_rover.buff_time}'
            )
        self.logger.info(
            f'phoebe: team={self.team} rover_form={rover_form} '
            f'pending={self._rover_form_pending}'
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
        if self.team in (1, 2) and self.char_zani is not None:
            return self.char_zani.get_state()

    def reset_action(self, new_rotation=True):
        if self.attribute == 2 and new_rotation:
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
