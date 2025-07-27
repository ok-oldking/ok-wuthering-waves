import time

from src.char.BaseChar import BaseChar, Priority


class Phrolova(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_liberation = -1

    def skip_combat_check(self):
        return self.time_elapsed_accounting_for_freeze(self.last_liberation) < 2

    def do_perform(self):
        self.last_liberation = -1
        if self.has_intro:
            if self.check_outro() in {'char_cantarella'}:
                self.do_perform_outro()
                return self.switch_next_char()
            self.continues_normal_attack(0.8)
        if self.flying():
            self.wait_down()
        if self.click_liberation():
            return self.switch_next_char()
        if self.heavy_and_liber():           
            return self.switch_next_char()
        self.continues_normal_attack(3, click_resonance_if_ready_and_return=True)
        self.click_echo()
        self.switch_next_char()

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if self.time_elapsed_accounting_for_freeze(self.last_liberation) > 8 and has_intro and current_char.char_name in {'char_cantarella'}:
            return Priority.MAX
        if self.time_elapsed_accounting_for_freeze(self.last_liberation) < 24:
            return Priority.MIN
        return Priority.FAST_SWITCH

    def resonance_available(self, current=None, check_ready=False, check_cd=False):
        return not (self.flying() or self.has_cd('resonance'))

    def heavy_and_liber(self):
        if self.heavy_click_forte(check_fun=self.is_mouse_forte_full):
            self.logger.debug('Phrolova heavy_click_forte')
            self.task.wait_until(self.click_liberation, time_out=3)
            return True
            
    def do_perform_outro(self):
        if self.flying():
            self.wait_down()
        if self.click_liberation():
            return
        self.continues_normal_attack(0.5)
        while self.time_elapsed_accounting_for_freeze(self.last_perform) < 16:
            if self.click_liberation():
                return
            if self.heavy_and_liber():           
                return self.switch_next_char()
            self.click_echo()  
            if self.resonance_available():
                self.click_resonance()
            self.task.click()
            self.check_combat()
            self.task.next_frame()
