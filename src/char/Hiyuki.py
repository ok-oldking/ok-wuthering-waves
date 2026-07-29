import time
from src.char.BaseChar import BaseChar, SwitchPriority

class Hiyuki(BaseChar):
    # 在场/阶段总超时 (秒)
    FIELD_TIME_OUT: float = 16.0
    # Linnai BUFF 时长 (秒)
    LINNAI_FIELD_TIME_OUT: float = 18.0
    # hold_liberation 长按的总超时 (秒)
    HOLD_LIB_TIME_OUT: float = 8.0
    # lib1 CD ≤ 此值 (秒) 才进 perform_standard
    STANDARD_LIB_CD_MAX: float = 3.5
    # 入场起手普攻时长 (秒)
    INTRO_NORMAL_ATTACK_TIME: float = 1.0
    # 共鸣后接的普攻时长 (秒)
    POST_RES_NORMAL_ATTACK_TIME: float = 0.3
    # 放完大招后、切人前的 settle (秒)
    POST_LIB_SETTLE: float = 0.5
    # 居合计数达此值才放 lib2 二命以下改为3
    LIB2_KENDO_COUNT: int = 4
    # lib2 CD 等待时间 (秒)
    HOLD_LIB_CD_WAIT: float = 1.5
    # 重击/大招前等"重新锁定敌人(has_long_action2)"的最长等待 (秒): 超时仍未锁上则跳过本次, 不空招
    WAIT_LOCK_TIME_OUT: float = 2.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lib_permission = True
        # 记录 Lib2 居合判定的次数
        self.lib2_count = 0

    def switch_out(self, con_full=False):
        """角色切出时重置状态"""
        super().switch_out(con_full)
        self.lib2_count = 0

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(self.INTRO_NORMAL_ATTACK_TIME)

        if self.has_long_action() and self.task.get_cd('liberation') <= self.STANDARD_LIB_CD_MAX:
            self.perform_standard()

        if self.has_long_action2():
            lib_success = self.perform_lib()
            if lib_success:
                self.sleep(self.POST_LIB_SETTLE)
                self.switch_next_char()
                return

            elif self.lib_permission and self.liberation_available():
                if self.hold_liberation():
                    self.sleep(self.POST_LIB_SETTLE)
                    self.switch_next_char()
                    return

        self.switch_next_char()

    def perform_standard(self):
        timeout = self.FIELD_TIME_OUT
        if self.has_intro and self.check_outro() == 'char_linnai':
            timeout = self.LINNAI_FIELD_TIME_OUT

        while self.has_long_action() and self.time_elapsed_accounting_for_freeze(self.last_perform) < timeout:
            self.click_echo(time_out=0)
            self.click_resonance(send_click=False, time_out=0)

            if self.liberation_available():
                if self.click_liberation():
                    self.logger.debug('hiyuki perform lib1')
                    return

            if self.is_mouse_forte_full():
                self.task.click(key="right")
                self.heavy_click_forte(check_fun=self.is_mouse_forte_full)
                self.task.wait_until(self.liberation_available, post_action=self.click_with_interval, time_out=self.FIELD_TIME_OUT)
                if self.click_liberation():
                    self.logger.debug('hiyuki perform lib1')
                    return
            else:
                self.click(interval=0.1)
            self.sleep(0.05)

    def perform_lib(self):
        start = time.time()
        timeout = self.FIELD_TIME_OUT
        if self.has_intro and self.check_outro() == 'char_linnai':
            timeout = self.LINNAI_FIELD_TIME_OUT

        is_timeout = False

        while self.has_long_action2() and self.time_elapsed_accounting_for_freeze(start) < timeout:
            self.f_break()
            self.click_echo(time_out=0)
            
            # 优化图像识别日志和复用
            lib_heavy_avail = self.lib_heavy_available()
            self.logger.debug(f"hiyuki find mouse_forte: {lib_heavy_avail}")

            is_timeout = self.time_elapsed_accounting_for_freeze(start) >= timeout - 0.5
            if self.lib_permission and self.liberation_available() and (self.lib2_count >= self.LIB2_KENDO_COUNT or is_timeout):
                if self.hold_liberation():
                    self.logger.info(f'hiyuki perform lib2 after heavy (count: {self.lib2_count}, timeout: {is_timeout})')
                    self.lib2_count = 0
                    return True

            # 注意确认 click_resonance 的返回值类型，防止 TypeError
            res_resonance = self.click_resonance(send_click=False, time_out=0)
            if res_resonance and res_resonance[0]:
                if is_timeout:
                    break
                self.continues_normal_attack(self.POST_RES_NORMAL_ATTACK_TIME)
            elif self.lib_heavy_available():
                if is_timeout:
                    break
                if self.wait_locked(self.WAIT_LOCK_TIME_OUT):
                    self.heavy_click_forte(check_fun=self.lib_heavy_available)
                if self.task.wait_until(self.liberation_available, post_action=self.click, time_out=0.5):
                    if self.wait_locked(self.WAIT_LOCK_TIME_OUT) and self.hold_liberation():
                        self.logger.debug('hiyuki perform lib2 (after heavy)')
                        self.lib2_count = 0
                        return True
                self.lib2_count += 1
                self.sleep(0.1)
                self.logger.debug(f"hiyuki heavy  count: {self.lib2_count}")
            elif bool(self.task.find_one('hiyuki_left', threshold=0.5)):
                self.task.wait_until(lambda: not bool(self.task.find_one('hiyuki_left', threshold=0.5)),
                                     post_action=self.click, time_out=3.0)
                if is_timeout:
                    break
                self.sleep(0.1)
            elif bool(self.task.find_one('hiyuki_right', threshold=0.5)):
                self.task.click(key="right", interval=1.0)
                self.sleep(0.1)
            else:
                self.click()

            self.sleep(0.05)
        
        # 循环外的兜底判定
        if self.lib_permission and self.liberation_available():
            if self.hold_liberation():
                self.logger.warning('hiyuki perform lib2 (final fallback)')
                self.lib2_count = 0
                return True

        return False

    def lib_heavy_available(self):
        return bool(self.task.find_one('hiyuki_lib_forte', threshold=0.7))

    def wait_locked(self, time_out):
        """等到重新锁定敌人(has_long_action2 为真)再返回 True; 等满 time_out 仍未锁上返回 False。

        期间用 post_action=self.click 持续普攻——既维持/重新锁定敌人, 又不空转。
        用于重击/大招前: 避免在"敌人刚死、新敌未锁"的窗口里空放。
        """
        return bool(self.task.wait_until(self.has_long_action2, post_action=self.click, time_out=time_out))

    def hold_liberation(self):
        if not self.task.use_liberation:
            return False
        last_click = 0
        self.logger.debug('hold_liberation start')
        start = time.time()
        while self.task.in_team()[0] and (self.liberation_available() or self.task.get_cd('liberation') <= self.HOLD_LIB_CD_WAIT) and time.time() - start < self.HOLD_LIB_TIME_OUT:
            if time.time() - start > last_click:
                self.task.send_key_down(self.get_liberation_key())
                last_click += 0.2
            self.sleep(0.05)
        self.task.in_liberation = True
        self.task.send_key_up(self.get_liberation_key())
        self.task.wait_until(lambda: self.task.in_team()[0], time_out=3)
        self.task.in_liberation = False
        self.add_freeze_duration(start, time.time() - start)
        self.logger.info(f'hold_liberation end {time.time() - start}')
        return True

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if has_intro and current_char and current_char.char_name in {'char_linnai', 'char_lucilla'}:
            return SwitchPriority.MUST
        return super().get_switch_priority(current_char, has_intro, target_low_con)
