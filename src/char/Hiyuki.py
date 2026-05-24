import time

from src.char.BaseChar import BaseChar, SwitchPriority

class Hiyuki(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lib_permission = True

    def do_perform(self):
        if self.has_intro:
            self.continues_normal_attack(1)
        if self.has_long_action2() and self.lib_permission and self.liberation_available():
            self.hold_liberation()
        if self.has_long_action() and not self.has_cd('liberation'):
            self.perform_standard()
        if self.has_long_action2():
            self.perform_lib()
        self.switch_next_char()
            
            
    def perform_standard(self):        
        timeout = 6
        if self.has_intro and self.check_outro() in {'char_linnai'}:
            timeout = 18
        while self.has_long_action() and self.time_elapsed_accounting_for_freeze(self.last_perform) < timeout:
            self.click_echo(time_out=0)
            if self.click_liberation():
                self.logger.debug('hiyuki perform lib1')
                self.lib_permission = False
                return
            if self.is_mouse_forte_full():
                self.task.click(key="right")
                self.heavy_click_forte(check_fun=self.is_mouse_forte_full)
                self.task.wait_until(self.liberation_available, post_action=self.click_with_interval, time_out=6)
                if self.click_liberation():
                    self.logger.debug('hiyuki perform lib1')
                    self.lib_permission = False
                    return
            self.click_resonance(send_click=False, time_out=0)
            self.click(interval=0.1)
            self.sleep(0.05)
            
    def perform_lib(self):  
        start = time.time()
        timeout = 6
        if self.has_intro and self.check_outro() in {'char_linnai'}:
            timeout = 18
        while self.has_long_action2() and self.time_elapsed_accounting_for_freeze(self.last_perform) < timeout:
            self.f_break()
            self.click_echo(time_out=0)
            self.logger.debug(f'hiyuki find mouse_forte{self.task.find_one('hiyuki_lib_forte', threshold=0.7)}')
            if self.lib_permission and self.liberation_available():
                self.hold_liberation()
                self.logger.debug('hiyuki perform lib2')
                return
            if self.click_resonance(send_click=False, time_out=0)[0]:
                if timeout == 6 and self.time_elapsed_accounting_for_freeze(start) > 2:
                    return
                self.continues_normal_attack(0.3)
            elif self.lib_heavy_available():
                self.heavy_click_forte(check_fun=self.lib_heavy_available)
                self.lib_permission = True
                if self.task.wait_until(self.liberation_available, post_action=self.click, time_out=0.5):
                    self.hold_liberation()
                    self.logger.debug('hiyuki perform lib2')
                return
            elif bool(self.task.find_one('hiyuki_left', threshold=0.5)):
                self.task.wait_until(lambda: not bool(self.task.find_one('hiyuki_left', threshold=0.5)),
                 post_action=self.click, time_out=3)
                if timeout == 6 and self.time_elapsed_accounting_for_freeze(start) > 2:
                    return 
                self.sleep(0.1)
            elif bool(self.task.find_one('hiyuki_right', threshold=0.5)):
                self.task.click(key="right")
                self.sleep(0.1)
            else:
                self.click()           
            self.sleep(0.05)
            
    def lib_heavy_available(self):
        return bool(self.task.find_one('hiyuki_lib_forte', threshold=0.7))
        
    def hold_liberation(self):
        if not self.task.use_liberation:
            return False
        last_click = 0
        self.logger.debug('hold_liberation start')
        start = time.time()
        while self.task.in_team()[0] and self.liberation_available() and time.time() - start < 8:  
            if time.time() - start > last_click:
                self.task.send_key_down(self.get_liberation_key())
                last_click += 0.5
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
        if has_intro and current_char and current_char.char_name in {'char_linnai'}:
            return SwitchPriority.MUST
        return super().get_switch_priority(current_char, has_intro, target_low_con)
