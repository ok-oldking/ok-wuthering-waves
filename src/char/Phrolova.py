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
        perform_under_outro = False
        if self.has_intro:
            if self.check_outro() in {'char_cantarella'}:
                perform_under_outro = True
            else:
                self.continues_normal_attack(0.8)
        if self.flying():
            self.wait_down() 
        start = time.time()
        timeout = lambda: time.time() - start < 4
        if perform_under_outro:
            self.continues_normal_attack(0.5)
            self.click_echo()
            timeout = lambda: self.time_elapsed_accounting_for_freeze(self.last_perform) < 16
        while timeout():
            if self.click_liberation():
                return self.switch_next_char()
            if self.flying():
                self.shorekeeper_auto_dodge()
            if self.heavy_and_liber():
                return self.switch_next_char()
            if self.resonance_available():
                self.click_resonance()
                if not perform_under_outro:
                    break
            self.task.click()
            self.check_combat()
            self.task.next_frame()
        if self.echo_available():
            self.sleep(0.3)
            self.click_echo()
        self.switch_next_char()

    def do_get_switch_priority(self, current_char: BaseChar, has_intro=False, target_low_con=False):
        if self.time_elapsed_accounting_for_freeze(self.last_liberation) > 12 and has_intro and current_char.char_name in {'char_cantarella'}:
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

    def shorekeeper_auto_dodge(self):
        from src.char.ShoreKeeper import ShoreKeeper
        for i, char in enumerate(self.task.chars):
            if isinstance(char, ShoreKeeper):
                return char.auto_dodge(condition = self.flying)   
