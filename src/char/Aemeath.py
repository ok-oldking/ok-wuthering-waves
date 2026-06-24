import time

from src.char.BaseChar import BaseChar, SwitchPriority


class Aemeath(BaseChar):
    LIBERATION_COOLDOWN = 25
    LIBERATION_FORCE_DURATION = 30
    LIB2_PREPARE_WINDOW = 8
    INTRO_LIBERATION_DELAY = 14
    MORNYE_NAMES = {'char_moning', 'char_moning_new'}
    POST_LIB2_COMBO_TIME_OUT = 1.5  # lib2 收尾连招(3A+E)的硬时间上限(秒), 防卡死/异常

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.should_wait = False
        self.intro_time = -1
        self.last_liber = -1
        self.last_enhance_e = -1
        self.intro_liberation_time = -1
        self.pending_lib2 = False
        self._lib1_cast_count = 0   # 本轮 lib1 释放次数
        self._lib2_cast_count = 0   # 本轮 lib2 释放次数

    def lib2_cooldown_anchor(self):
        if self.last_liber >= 0:
            return self.last_liber
        combat_start = getattr(self.task, 'combat_start', -1)
        return combat_start if combat_start > 0 else -1

    def lib2_cooldown_left(self):
        anchor = self.lib2_cooldown_anchor()
        if anchor < 0:
            return 0
        elapsed = self.time_elapsed_accounting_for_freeze(anchor)
        return max(0, self.LIBERATION_COOLDOWN - elapsed)

    def liberation_cooldown_left(self):
        if self.last_liber < 0:
            return 0
        elapsed = self.time_elapsed_accounting_for_freeze(self.last_liber)
        return max(0, self.LIBERATION_COOLDOWN - elapsed)

    def lib1_unlock_anchor(self):
        if self.last_liber >= 0:
            return self.last_liber
        return getattr(self.task, 'combat_start', -1)

    def record_intro_liberation(self):
        self.intro_liberation_time = time.time()

    def intro_lib1_ready(self):
        return self.intro_liberation_time >= 0 and (
                self.time_elapsed_accounting_for_freeze(self.intro_liberation_time)
                <= self.INTRO_LIBERATION_DELAY)

    def lib1_unlocked(self):
        if self.intro_lib1_ready():
            return True
        anchor = self.lib1_unlock_anchor()
        return anchor >= 0 and (
                self.time_elapsed_accounting_for_freeze(anchor) >= self.LIBERATION_FORCE_DURATION)

    def can_cast_lib1(self):
        return self.liberation_cooldown_left() <= 0 and self.lib1_unlocked()

    def can_cast_liberation(self):
        return self.can_cast_lib1()

    def lib2_available(self):
        return bool(self.task.find_one('aemeath_lib2', threshold=0.7))

    def preparing_lib2(self):
        return self.lib2_cooldown_anchor() >= 0 and (
                self.lib2_cooldown_left() < self.LIB2_PREPARE_WINDOW)

    def should_wait_for_lib2(self):
        return self.pending_lib2 or self.preparing_lib2()

    def should_wait_for_enhance_e(self):
        return self.time_elapsed_accounting_for_freeze(self.last_enhance_e) > 12

    def record_enhance_e(self):
        self.last_enhance_e = time.time()

    def record_heavy_liberation(self):
        self.pending_lib2 = True

    def record_liberation(self, is_lib2):
        if is_lib2:
            self.pending_lib2 = False
            self.last_liber = time.time()
            self.last_enhance_e = self.last_liber
            self._lib2_cast_count += 1
        else:
            self.intro_liberation_time = -1
            self._lib1_cast_count += 1

    def _lib1_cast_this_turn(self):
        """本轮上场后是否已释放过 lib1（第一次解放）。"""
        return self._lib1_cast_count > 0

    def _lib2_cast_this_turn(self):
        """本轮上场后是否已释放过 lib2（第二次解放）。"""
        return self._lib2_cast_count > 0

    def _execute_lib2_guard(self, context_log: str = "") -> None:
        """
        进入等待循环以确保第二次解放（lib2）被释放。
        包含 13 秒的超时保护机制，防止长时间死循环。
        """
        lib2_guard_start = time.time()
        self.logger.info(f'Aemeath [do_perform] waiting for lib2 before switching {context_log}')
        
        while not self._lib2_cast_this_turn():
            # 超时保护（13秒），防止 lib2 长时间不就绪导致死循环
            if time.time() - lib2_guard_start > 13:
                self.logger.warning(f'Aemeath [do_perform] lib2 guard timed out (13s) {context_log}, casting switch')
                break
                
            self.check_combat()
            if self.handle_heavy():
                self.logger.debug(f'Aemeath [do_perform] handle_heavy triggered during lib2 guard {context_log}')
                self.task.next_frame()
                continue
                
            if self.lib2_available():
                if self.lib():
                    self.logger.debug(f'Aemeath [do_perform] lib2 cast, integrity guard satisfied {context_log}')
                    break
                    
            if self.enhance_e_available():
                self.click_resonance(has_animation=True, send_click=True,
                                     animation_min_duration=0.5, time_out=1.5)
            self.click(after_sleep=0.01)
            self.task.next_frame()

    def _execute_lib1_or_fallback_guard(self) -> None:
        """
        处理本轮尚未释放任何解放（lib1）的情况。
        在 8 秒窗口内尝试释放 lib1 或共鸣技能。如果成功释放 lib1，则级联调用 lib2 守护。
        """
        lib_guard_start = time.time()
        found_action = False

        while time.time() - lib_guard_start < 10.0:
            self.check_combat()
            
            if self.liberation_available() and self.can_cast_lib1():
                self.logger.debug('Aemeath [do_perform] lib available but not cast — casting lib1')
                self.lib()
                found_action = True 
                # 成功释放 lib1 后，直接复用 lib2 的等待逻辑
                self._execute_lib2_guard(context_log="(after forced lib1)")
                break
                
            elif self.enhance_e_available():
                self.logger.info('Aemeath [do_perform] resonance available but not cast — casting resonance')
                self.click_resonance(has_animation=True, send_click=True,
                                     animation_min_duration=0.5, time_out=1.5)
                found_action = True
                break
                
            else:
                if not self.handle_heavy():
                    self.click(after_sleep=0.01)
                self.task.next_frame()

        if not found_action:
            self.logger.warning(
                'Aemeath [do_perform] 8s window elapsed with no available skill, '
                'allowing switch without liberation'
            )

    def _execute_post_lib2_combo(self):
        """lib2 释放后的强制收尾连招: 3次普攻 + 共鸣技能(E)。

        整段受 POST_LIB2_COMBO_TIME_OUT(1.5s) 硬上限保护, 防止收尾卡死/异常拖住战斗循环。
        """
        self.logger.info('Aemeath [post-lib2 combo] starting: 3 Normal Attacks -> Resonance (E)')
        start = time.time()

        # 最多 3 次普攻; 每次前检查战斗状态与时间预算, 超时即停.
        for _ in range(3):
            if time.time() - start >= self.POST_LIB2_COMBO_TIME_OUT:
                self.logger.info('Aemeath [post-lib2 combo] time budget reached during attacks, stopping')
                return
            self.check_combat()
            self.normal_attack()
            self.sleep(0.35)

        self.check_combat()

        remaining = self.POST_LIB2_COMBO_TIME_OUT - (time.time() - start)
        if remaining <= 0:
            self.logger.info('Aemeath [post-lib2 combo] no time budget left for E, skipping')
            return
        e_available = self.enhance_e_available() or not self.task.has_cd('resonance')
        if e_available:
            self.logger.info('Aemeath [post-lib2 combo] E available, casting resonance')
            self.click_resonance(has_animation=True, send_click=True,
                                 animation_min_duration=0.5, time_out=remaining)
            self.record_enhance_e()
        else:
            self.logger.info('Aemeath [post-lib2 combo] E not available, skipping')


    def _process_end_of_turn_liberations(self) -> None:
        """根据当前回合的解放技能释放状态，进行决策路由并执行相应的收尾动作。"""
        if self._lib1_cast_this_turn() and not self._lib2_cast_this_turn():
            # ── 分支A：本轮已释放 lib1 但未释放 lib2，必须等待并释放 lib2 ───────
            self._execute_lib2_guard(context_log="(initial lib1 cast)")
            
        elif not self._lib1_cast_this_turn() and not self._lib2_cast_this_turn():
            # ── 分支B：本轮既未释放 lib1 也未释放 lib2，尝试 8 秒 fallback ──────
            self._execute_lib1_or_fallback_guard()

    def do_perform(self):
        self.intro_time = -1
        self.should_wait = False
        # 重置本轮计数
        self._lib1_cast_count = 0
        self._lib2_cast_count = 0
        
        if self.has_intro:
            self.record_intro_liberation()
            self.continues_normal_attack(1.2)
            if self.check_outro() in {'char_linnai', 'char_lupa'}:
                self.intro_time = 14
            if self.check_outro() in {'chang_changli', 'char_changli2'}:
                self.intro_time = 10
                
        self.perform_everything()

        # 处理回合末尾的技能链（lib1 -> lib2）的完整性约束
        self._process_end_of_turn_liberations()

        self.switch_next_char()

    def lib(self):
        is_lib2 = self.lib2_available()
        if not is_lib2 and not self.can_cast_lib1():
            return False
        if not self.click_liberation(wait_if_cd_ready=0):
            return False
        self.record_liberation(is_lib2)
        self.f_break()

        if is_lib2:
            self._execute_post_lib2_combo()
        return True

    def continue_in_intro(self):
        return self.time_elapsed_accounting_for_freeze(self.last_liber) < 30 and \
            self.time_elapsed_accounting_for_freeze(self.last_perform) < self.intro_time

    def perform_everything(self):
        start = time.time()
        self.should_wait = self.should_wait_for_lib2() or self.should_wait_for_enhance_e()
        if not self.should_wait:
            self.should_wait = self.has_intro and self.liberation_cooldown_left() < 12
        while self.time_elapsed_accounting_for_freeze(start) < 1.2 or (
                self.should_wait and self.time_elapsed_accounting_for_freeze(start) < 3.6):
            self.cycle_start()
            if self.handle_heavy():
                self.f_break()
                start = time.time()
                self.should_wait = self.should_wait_for_lib2()
                self.task.next_frame()
                continue
            if self.intro_lib1_ready() and self.lib():
                start = time.time()
                self.should_wait = self.should_wait_for_lib2()
            elif self.enhance_e_available():
                if self.click_resonance(has_animation=True, send_click=True, animation_min_duration=0.5,
                                        time_out=1.5)[0]:
                    self.record_enhance_e()
                    self.click_echo(time_out=0)
                    self.f_break()
                    self.task.next_frame()
                if (
                        self.intro_lib1_ready() and self.can_cast_lib1() and self.liberation_available()) or self.has_long_action():
                    start = time.time()
                else:
                    self.click(after_sleep=0.01)
                    return
            elif self.lib():
                start = time.time()
                self.should_wait = self.should_wait_for_lib2()
                continue
            else:
                self.click()
            self.cycle_sleep()

    def lib_cd_eminent(self):
        cd = self.task.get_cd('liberation')
        return self.lib1_unlocked() and (0 < cd < 1.5 or self.liberation_available())

    def enhance_e_available(self):
        return self.task.find_one('aemeath_e1', threshold=0.7) or self.task.find_one('aemeath_e2',
                                                                                     threshold=0.7)

    def heavy_wait_highlight_down(self):
        self.task.mouse_down()
        ret = self.task.wait_until(lambda: not self.has_long_action(), time_out=1.2)
        self.task.mouse_up()
        self.sleep(0.01)
        return ret

    def handle_heavy(self):
        if not self.has_long_action():
            return False
        prepares_lib2 = self.preparing_lib2()
        if self.heavy_wait_highlight_down():
            if prepares_lib2:
                self.record_heavy_liberation()
            return True
        return False

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if self.should_wait_for_lib2():
            # Mornye 离场且队里有 Linnai 时让位: Linnai 要吃 Mornye 协奏入场, 优先级最高, Aemeath 此刻
            # 不抢 MUST(否则两者都 MUST、按"最久未上场"决胜会切到 Aemeath). lib2 顺延到下次轮到 Aemeath.
            from src.char.Linnai import Linnai
            if current_char and current_char.char_name in self.MORNYE_NAMES and self.task.has_char(Linnai):
                return super().get_switch_priority(current_char, has_intro, target_low_con)
            return SwitchPriority.MUST
        return super().get_switch_priority(current_char, has_intro, target_low_con)

    def on_combat_end(self, chars):
        self.switch_other_char()