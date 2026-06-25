import time
from src.char.BaseChar import BaseChar, SwitchPriority

class Hiyuki(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lib_permission = True
        # 记录 Lib2 居合判定的次数
        self.lib2_count = 0
        self.time_out = 14.5

    def switch_out(self, con_full=False):
        """角色切出时重置状态"""
        super().switch_out(con_full)
        self.lib2_count = 0

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1)

        if self.has_long_action() and not self.has_cd('liberation'):
            self.perform_standard()

        if self.has_long_action2():
            lib_success = self.perform_lib()
            if lib_success:
                self.sleep(0.5)
                self.switch_next_char()
                return  

            elif self.lib_permission and self.liberation_available():
                if self.hold_liberation():
                    self.sleep(0.5)
                    self.switch_next_char()
                    return

        self.switch_next_char()

    def perform_standard(self):
        timeout = self.time_out
        if self.has_intro and self.check_outro() in {'char_linnai'}:
            timeout = 18.0

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
                self.task.wait_until(self.liberation_available, post_action=self.click_with_interval, time_out=self.time_out)
                if self.click_liberation():
                    self.logger.debug('hiyuki perform lib1')
                    return
            else:
                self.click(interval=0.1)
            self.sleep(0.05)

    def perform_lib(self):
        start = time.time()
        timeout = self.time_out
        if self.has_intro and self.check_outro() in {'char_linnai'}:
            timeout = 18.0

        is_timeout = False

        while self.has_long_action2() and self.time_elapsed_accounting_for_freeze(start) < timeout:
            self.f_break()
            self.click_echo(time_out=0)
            self.logger.debug(f"hiyuki find mouse_forte{self.task.find_one('hiyuki_lib_forte', threshold=0.7)}")

            # 终结技释放判定 (最高优先级，确保满足条件时立刻执行)
            is_timeout = self.time_elapsed_accounting_for_freeze(start) >= timeout - 0.5
            if self.lib_permission and self.liberation_available() and (self.lib2_count >= 4 or is_timeout):
                if self.hold_liberation():
                    self.logger.info(f'hiyuki perform lib2 after heavy (count: {self.lib2_count}, timeout: {is_timeout})')
                    self.lib2_count = 0
                    return True

            # 提高共鸣技能释放优先级
            if self.click_resonance(send_click=False, time_out=0)[0]:
                if is_timeout:
                    break
                self.continues_normal_attack(0.3)
            elif self.lib_heavy_available():
                self.heavy_click_forte(check_fun=self.lib_heavy_available)
                if self.task.wait_until(self.liberation_available, post_action=self.click, time_out=0.5):
                    if self.hold_liberation():
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
        
        # 循环外的兜底判定 (防止循环退出时大招刚好就绪)
        if self.lib_permission and self.liberation_available():
            if self.hold_liberation():
                self.logger.warning('hiyuki perform lib2 (final fallback)')
                self.lib2_count = 0
                return True

        return False

    def lib_heavy_available(self):
        return bool(self.task.find_one('hiyuki_lib_forte', threshold=0.7))

    def hold_liberation(self):
        if not self.task.use_liberation:
            return False
        last_click = 0
        self.logger.debug('hold_liberation start')
        start = time.time()
        while self.task.in_team()[0] and self.liberation_available() and time.time() - start < 8.0:
            if time.time() - start > last_click:
                self.task.send_key_down(self.get_liberation_key())
                last_click += 0.2
            if self.task.in_team()[0]:
                self.sleep(0.05)
        self.task.in_liberation = True
        self.task.send_key_up(self.get_liberation_key())
        self.task.wait_until(lambda: self.task.in_team()[0], time_out=3)
        self.task.in_liberation = False
        self.add_freeze_duration(start, time.time() - start)
        self.logger.info(f'hold_liberation end {time.time() - start}')
        return True

    def get_switch_priority(self, current_char=None, has_intro=False, target_low_con=False):
        if has_intro and current_char and (current_char.char_name in {'char_linnai'} or current_char.char_name in {'char_lucilla'}):
            return SwitchPriority.MUST
        return super().get_switch_priority(current_char, has_intro, target_low_con)