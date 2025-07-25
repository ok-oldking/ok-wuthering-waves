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
            self.continues_normal_attack(0.5)
        if self.flying():
            self.wait_down()
        if self.click_liberation():
            return self.switch_next_char()
        elif self.heavy_click_forte(check_fun=self.is_mouse_forte_full):
            self.logger.debug('Phrolova heavy_click_forte')
            return self.switch_next_char()
        self.continues_normal_attack(3, click_resonance_if_ready_and_return=True)
        self.click_echo()
        self.switch_next_char()

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if self.time_elapsed_accounting_for_freeze(self.last_liberation) < 24:
            return Priority.MIN
        return Priority.FAST_SWITCH
        # return super().do_get_switch_priority(current_char, has_intro)

    def resonance_available(self, current=None, check_ready=False, check_cd=False):
        return not (self.flying() or self.has_cd('resonance'))
